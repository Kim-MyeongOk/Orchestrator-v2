import asyncio
import json
import uuid

from typing             import Dict
from typing             import Optional
from typing             import Any
from dataclasses        import asdict
from typing             import List
from datetime           import datetime
from datetime           import timezone
from redis.exceptions   import RedisError
from asyncpg.exceptions import UniqueViolationError
from asyncpg.exceptions import PostgresError

from common.cache.redis_stream.redis_stream_client import RedisStreamClient
from common.identifier.uuid_v7.uuid_v7_generator   import UUIDV7Generator
from app.llm.job.job_configuration                 import JobConfiguration
from app.llm.agent.model_configuration             import ModelConfiguration
from app.llm.repository.job_repository             import JobRepository
from app.llm.repository.job_message_repository     import JobMessageRepository
from app.llm.repository.job_event_repository       import JobEventRepository
from app.llm.repository.job_chunk_repository       import JobChunkRepository
from app.llm.repository.job_task_repository        import JobTaskRepository
from app.llm.repository.chat_thread_repository     import ChatThreadRepository
from app.llm.repository.thread_message_repository  import ThreadMessageRepository
from app.llm.job.job_executor.job_executor         import JobExecutor
from app.llm.job.job_transfer.job_transfer         import JobTransfer
from common.cache.redis_stream.redis_key_builder   import RedisKeyBuilder
from app.llm.job.job_manager.job_status            import JobStatus
from app.llm.job.job_manager.job_not_found_error   import JobNotFoundError
from app.llm.job.job_manager.job_type              import JobType
from app.llm.job.job_manager.job_ownership_error   import JobOwnershipError
from app.llm.job.job_manager.job_duplicate_error   import JobDuplicateError
from app.llm.job.job_manager.job_state_error       import JobStateError

class JobManager:
    def __init__(self, redis_stream_client : RedisStreamClient, uuid_v7_generator : UUIDV7Generator, job_configuration : JobConfiguration, default_model_configuration : ModelConfiguration, job_repository : JobRepository, job_message_repository : JobMessageRepository, job_event_repository : JobEventRepository, job_chunk_repository : JobChunkRepository, job_task_repository : JobTaskRepository, chat_thread_repository : ChatThreadRepository, thread_message_repository : ThreadMessageRepository, job_executor : JobExecutor, job_transfer : JobTransfer) -> None:
        self.redis_stream_client          = redis_stream_client
        self.uuid_v7_generator            = uuid_v7_generator
        self.job_configuration            = job_configuration
        self.default_model_configuration  = default_model_configuration
        self.job_repository               = job_repository
        self.job_message_repository       = job_message_repository
        self.job_event_repository         = job_event_repository
        self.job_chunk_repository         = job_chunk_repository
        self.job_task_repository          = job_task_repository
        self.chat_thread_repository       = chat_thread_repository
        self.thread_message_repository    = thread_message_repository
        self.job_executor                 = job_executor
        self.job_transfer                 = job_transfer
        self._task_dictionary             : Dict[str, asyncio.Task[None]] = {}
        self._cancel_reason_dictionary    : Dict[str, str] = {}

    def _get_model_configuration(self, model_override_dictionary : Optional[Dict[str, Any]]) -> ModelConfiguration:
        model_configuration_dictionary = asdict(self.default_model_configuration)
        if model_override_dictionary is not None:
            override_provider = model_override_dictionary.get("provider")
            if override_provider is not None and override_provider != self.default_model_configuration.provider:
                for provider_field_name in ("api_key", "base_url", "default_header_dictionary", "extra_body_dictionary"):
                    model_configuration_dictionary[provider_field_name] = None
            for field_name, field_value in model_override_dictionary.items():
                if field_value is not None:
                    model_configuration_dictionary[field_name] = field_value
        return ModelConfiguration(**model_configuration_dictionary)

    @staticmethod
    def _get_stored_request_payload(message_dictionary_list : List[Dict[str, Any]], model_configuration : ModelConfiguration, model_override_dictionary : Optional[Dict[str, Any]]) -> Dict[str, Any]:
        stored_model_dictionary : Dict[str, Any] = {
            "provider"   : model_configuration.provider,
            "model_name" : model_configuration.model_name
        }
        if model_override_dictionary is not None:
            stored_model_dictionary.update({field_name : field_value for field_name, field_value in model_override_dictionary.items() if field_value is not None and field_name not in {"api_key", "default_header_dictionary"}})
        return {
            "messages" : message_dictionary_list,
            "model"    : stored_model_dictionary
        }

    @staticmethod
    def _convert_meta_dictionary(meta_dictionary : Dict[str, str]) -> Dict[str, Any]:
        converted_dictionary : Dict[str, Any] = dict(meta_dictionary)
        for field_name in ("last_seq", "message_count", "event_count"):
            field_value = converted_dictionary.get(field_name)
            if field_value not in (None, ""):
                converted_dictionary[field_name] = int(field_value)
        usage_text = converted_dictionary.get("usage")
        if usage_text:
            converted_dictionary["usage"] = json.loads(usage_text)
        elif "usage" in converted_dictionary:
            converted_dictionary["usage"] = None
        if converted_dictionary.get("error_message") == "":
            converted_dictionary["error_message"] = None
        return converted_dictionary

    def _get_cancellation_reason(self, run_id_string : str) -> Optional[str]:
        return self._cancel_reason_dictionary.get(run_id_string)

    def _remove_finished_task(self, run_id_string : str, execution_task : asyncio.Task[None]) -> None:
        self._task_dictionary.pop(run_id_string, None)
        self._cancel_reason_dictionary.pop(run_id_string, None)
        if not execution_task.cancelled():
            execution_task.exception()

    async def _set_cancel_requested_async(self, run_id : uuid.UUID, cancellation_reason : str) -> None:
        run_id_string = str(run_id)
        self._cancel_reason_dictionary[run_id_string] = cancellation_reason
        is_updated = await self.redis_stream_client.request_job_cancellation_async(
            RedisKeyBuilder.get_job_meta_key(run_id_string),
            cancellation_reason,
            datetime.now(timezone.utc).isoformat()
        )
        if not is_updated:
            raise RedisError(f"ACTIVE JOB META NOT FOUND : {run_id}")

    async def _wait_for_terminal_async(self, run_id : uuid.UUID) -> Dict[str, Any]:
        maximum_wait_count = self.job_configuration.heartbeat_interval_second_count + 5
        for _wait_count in range(maximum_wait_count):
            job_dictionary = await self.job_repository.get_job_async(run_id)
            if job_dictionary is not None and JobStatus(job_dictionary["status"]).is_terminal():
                return job_dictionary
            await asyncio.sleep(1.0)
        job_dictionary = await self.job_repository.get_job_async(run_id)
        if job_dictionary is None:
            raise JobNotFoundError(f"JOB NOT FOUND : {run_id}")
        return job_dictionary

    @staticmethod
    async def _wait_for_execution_task_async(execution_task : asyncio.Task[None]) -> None:
        try:
            await asyncio.shield(execution_task)
        except asyncio.CancelledError:
            pass

    async def _ensure_terminal_async(self, job_dictionary : Dict[str, Any], job_status : JobStatus, error_message : Optional[str]) -> None:
        run_id                 = uuid.UUID(str(job_dictionary["run_id"]))
        current_job_dictionary = await self.job_repository.get_job_async(run_id)
        if current_job_dictionary is None or JobStatus(current_job_dictionary["status"]).is_terminal():
            return
        await self.job_transfer.transfer_async(
            run_id,
            uuid.UUID(str(job_dictionary["thread_id"])),
            job_status,
            error_message,
            None,
            []
        )

    async def submit_async(self, user_id : uuid.UUID, job_type : JobType, thread_id : Optional[uuid.UUID], message_dictionary_list : List[Dict[str, Any]], output_format : str, model_override_dictionary : Optional[Dict[str, Any]] = None, idempotency_key : Optional[str] = None) -> Dict[str, Any]:
        actual_thread_id     = thread_id or self.uuid_v7_generator.generate()
        thread_owner_user_id = await self.job_repository.get_thread_owner_user_id_async(actual_thread_id)
        if thread_owner_user_id is not None and thread_owner_user_id != str(user_id):
            raise JobOwnershipError(f"THREAD USER MISMATCH : {actual_thread_id}")
        if idempotency_key is not None:
            existing_job_dictionary = await self.job_repository.get_job_by_idempotency_key_async(idempotency_key)
            if existing_job_dictionary is not None:
                existing_run_id = existing_job_dictionary["run_id"] if existing_job_dictionary["user_id"] == str(user_id) else "UNKNOWN"
                raise JobDuplicateError(existing_run_id)
        run_id                     = self.uuid_v7_generator.generate()
        run_id_string              = str(run_id)
        lock_key : Optional[str]   = None
        model_configuration        = self._get_model_configuration(model_override_dictionary)
        request_payload_dictionary = JobManager._get_stored_request_payload(message_dictionary_list, model_configuration, model_override_dictionary)
        if idempotency_key is not None:
            lock_key    = RedisKeyBuilder.get_inflight_key(idempotency_key)
            is_acquired = await self.redis_stream_client.acquire_lock_async(lock_key, run_id_string, self.job_configuration.idempotency_lock_ttl_second_count)
            if not is_acquired:
                existing_run_id = await self.redis_stream_client.get_string_async(lock_key)
                visible_run_id  = "UNKNOWN"
                if existing_run_id is not None:
                    try:
                        existing_job_dictionary = await self.job_repository.get_job_async(uuid.UUID(existing_run_id))
                    except ValueError:
                        existing_job_dictionary = None
                    if existing_job_dictionary is not None and existing_job_dictionary["user_id"] == str(user_id):
                        visible_run_id = existing_run_id
                raise JobDuplicateError(visible_run_id)
        try:
            turn_number = await self.job_repository.insert_job_async(
                run_id,
                actual_thread_id,
                user_id,
                job_type.value,
                JobStatus.PENDING.value,
                output_format,
                request_payload_dictionary,
                idempotency_key
            )
            await self.chat_thread_repository.upsert_thread_on_submit_async(actual_thread_id, user_id, run_id, message_dictionary_list)
            await self.thread_message_repository.insert_user_message_list_async(self.uuid_v7_generator, actual_thread_id, run_id, turn_number, message_dictionary_list)
        except UniqueViolationError:
            if lock_key is not None:
                try:
                    await self.redis_stream_client.release_lock_async(lock_key, run_id_string)
                except RedisError:
                    pass
            existing_job_dictionary = await self.job_repository.get_job_by_idempotency_key_async(idempotency_key or "")
            existing_run_id         = "UNKNOWN"
            if existing_job_dictionary is not None and existing_job_dictionary["user_id"] == str(user_id):
                existing_run_id = existing_job_dictionary["run_id"]
            raise JobDuplicateError(existing_run_id)
        except ValueError as value_error:
            if lock_key is not None:
                try:
                    await self.redis_stream_client.release_lock_async(lock_key, run_id_string)
                except RedisError:
                    pass
            raise JobOwnershipError(str(value_error)) from value_error
        except PostgresError:
            if lock_key is not None:
                try:
                    await self.redis_stream_client.release_lock_async(lock_key, run_id_string)
                except RedisError:
                    pass
            raise
        created_at      = datetime.now(timezone.utc).isoformat()
        meta_dictionary = {
            "run_id"           : run_id_string,
            "thread_id"        : str(actual_thread_id),
            "user_id"          : str(user_id),
            "job_type"         : job_type.value,
            "status"           : JobStatus.PENDING.value,
            "output_format"    : output_format,
            "last_seq"         : "0",
            "heartbeat_at"     : created_at,
            "created_at"       : created_at,
            "updated_at"       : created_at,
            "error_message"    : "",
            "usage"            : "",
            "message_count"    : "0",
            "event_count"      : "0",
            "cancel_requested" : "0",
            "cancel_reason"    : ""
        }
        try:
            await self.redis_stream_client.set_hash_dictionary_with_expire_async(
                RedisKeyBuilder.get_job_meta_key(run_id_string),
                meta_dictionary,
                self.job_configuration.redis_safety_ttl_second_count
            )
        except RedisError:
            await self.job_repository.update_job_finished_async(run_id, JobStatus.FAILED.value, "REDIS INITIALIZATION FAILED", None, 0, 0)
            if lock_key is not None:
                try:
                    await self.redis_stream_client.release_lock_async(lock_key, run_id_string)
                except RedisError:
                    pass
            raise
        execution_task = asyncio.create_task(
            self.job_executor.execute_async(
                run_id,
                actual_thread_id,
                user_id,
                request_payload_dictionary,
                model_configuration,
                lambda : self._get_cancellation_reason(run_id_string)
            ),
            name = f"llm-job-{run_id_string}"
        )
        self._task_dictionary[run_id_string] = execution_task
        execution_task.add_done_callback(lambda finished_task : self._remove_finished_task(run_id_string, finished_task))
        return {
            "run_id"    : run_id_string,
            "thread_id" : str(actual_thread_id),
            "status"    : JobStatus.PENDING.value
        }

    async def get_job_async(self, run_id : uuid.UUID, user_id : uuid.UUID) -> Dict[str, Any]:
        job_dictionary = await self.job_repository.get_job_for_user_async(run_id, user_id)
        if job_dictionary is None:
            raise JobNotFoundError(f"JOB NOT FOUND : {run_id}")
        if JobStatus(job_dictionary["status"]).is_terminal():
            return job_dictionary
        meta_dictionary = await self.redis_stream_client.get_hash_dictionary_async(RedisKeyBuilder.get_job_meta_key(str(run_id)))
        if meta_dictionary:
            if JobStatus(meta_dictionary["status"]).is_terminal():
                terminal_job_dictionary = await self.job_repository.get_job_for_user_async(run_id, user_id)
                if terminal_job_dictionary is not None:
                    return terminal_job_dictionary
            return JobManager._convert_meta_dictionary(meta_dictionary)
        return job_dictionary

    async def get_persisted_job_async(self, run_id : uuid.UUID, user_id : uuid.UUID) -> Dict[str, Any]:
        job_dictionary = await self.job_repository.get_job_for_user_async(run_id, user_id)
        if job_dictionary is None:
            raise JobNotFoundError(f"JOB NOT FOUND : {run_id}")
        return job_dictionary

    async def get_job_result_async(self, run_id : uuid.UUID, user_id : uuid.UUID) -> Dict[str, Any]:
        job_dictionary = await self.get_job_async(run_id, user_id)
        if JobStatus(job_dictionary["status"]).is_terminal():
            job_dictionary["message_list"] = await self.job_message_repository.get_message_list_async(run_id)
            job_dictionary["event_list"  ] = await self.job_event_repository.get_event_list_async(run_id)
            job_dictionary["chunk_list"  ] = await self.job_chunk_repository.get_chunk_list_async(run_id)
            job_dictionary["task_list"   ] = await self.job_task_repository.get_task_list_async(run_id)
        return job_dictionary

    async def get_job_list_async(self, user_id : uuid.UUID, status : Optional[str], job_type : Optional[str], cursor_created_at : Optional[datetime], cursor_run_id : Optional[uuid.UUID], limit_count : int) -> List[Dict[str, Any]]:
        return await self.job_repository.get_job_list_async(user_id, status, job_type, cursor_created_at, cursor_run_id, limit_count)

    async def cancel_async(self, run_id : uuid.UUID, user_id : uuid.UUID) -> Dict[str, Any]:
        job_dictionary = await self.get_job_async(run_id, user_id)
        if JobStatus(job_dictionary["status"]).is_terminal():
            raise JobStateError(f"JOB ALREADY FINISHED : {run_id}")
        execution_task = self._task_dictionary.get(str(run_id))
        try:
            await self._set_cancel_requested_async(run_id, "cancelled")
        except RedisError:
            if execution_task is None:
                self._cancel_reason_dictionary.pop(str(run_id), None)
                await self._ensure_terminal_async(job_dictionary, JobStatus.CANCELLED, None)
                return await self.get_job_result_async(run_id, user_id)
        if execution_task is not None:
            execution_task.cancel()
            await JobManager._wait_for_execution_task_async(execution_task)
        else:
            await self._wait_for_terminal_async(run_id)
        await self._ensure_terminal_async(job_dictionary, JobStatus.CANCELLED, None)
        return await self.get_job_result_async(run_id, user_id)

    async def fail_client_disconnected_async(self, run_id : uuid.UUID, user_id : uuid.UUID) -> None:
        job_dictionary = await self.get_job_async(run_id, user_id)
        if JobStatus(job_dictionary["status"]).is_terminal():
            return
        execution_task = self._task_dictionary.get(str(run_id))
        try:
            await self._set_cancel_requested_async(run_id, "client_disconnected")
        except RedisError:
            if execution_task is None:
                self._cancel_reason_dictionary.pop(str(run_id), None)
                await self._ensure_terminal_async(job_dictionary, JobStatus.FAILED, "CLIENT DISCONNECTED")
                return
        if execution_task is not None:
            execution_task.cancel()
            await JobManager._wait_for_execution_task_async(execution_task)
        await self._ensure_terminal_async(job_dictionary, JobStatus.FAILED, "CLIENT DISCONNECTED")

    async def shutdown_async(self) -> None:
        run_id_string_list   = list(self._task_dictionary.keys())
        execution_task_list = list(self._task_dictionary.values())
        for run_id_string, execution_task in list(self._task_dictionary.items()):
            self._cancel_reason_dictionary[run_id_string] = "shutdown"
            execution_task.cancel()
        if execution_task_list:
            await asyncio.gather(*execution_task_list, return_exceptions = True)
        for run_id_string in run_id_string_list:
            run_id = uuid.UUID(run_id_string)
            job_dictionary = await self.job_repository.get_job_async(run_id)
            if job_dictionary is not None:
                await self._ensure_terminal_async(job_dictionary, JobStatus.FAILED, "SERVER SHUTDOWN")
