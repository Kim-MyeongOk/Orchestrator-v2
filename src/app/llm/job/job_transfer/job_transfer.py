import uuid
import json

from typing           import Any
from typing           import Dict
from typing           import Optional
from datetime         import datetime
from datetime         import timezone
from redis.exceptions import RedisError
from typing           import List

from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager
from common.cache.redis_stream.redis_stream_client      import RedisStreamClient
from common.identifier.uuid_v7.uuid_v7_generator        import UUIDV7Generator
from app.llm.job.job_configuration                      import JobConfiguration
from app.llm.repository.job_repository                  import JobRepository
from app.llm.repository.job_message_repository          import JobMessageRepository
from app.llm.repository.job_event_repository            import JobEventRepository
from app.llm.repository.job_chunk_repository            import JobChunkRepository
from app.llm.repository.job_task_repository             import JobTaskRepository
from app.llm.repository.chat_thread_repository          import ChatThreadRepository
from app.llm.repository.thread_message_repository       import ThreadMessageRepository
from app.llm.job.job_manager.job_status                 import JobStatus
from common.cache.redis_stream.redis_key_builder        import RedisKeyBuilder
from app.llm.stream_pipeline.usage_accumulator          import UsageAccumulator

class JobTransfer:
    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager, redis_stream_client : RedisStreamClient, uuid_v7_generator : UUIDV7Generator, job_configuration : JobConfiguration, job_repository : JobRepository, job_message_repository : JobMessageRepository, job_event_repository : JobEventRepository, job_chunk_repository : JobChunkRepository, job_task_repository : JobTaskRepository, chat_thread_repository : ChatThreadRepository, thread_message_repository : ThreadMessageRepository) -> None:
        self.postgresql_pool_manager   = postgresql_pool_manager
        self.redis_stream_client       = redis_stream_client
        self.uuid_v7_generator         = uuid_v7_generator
        self.job_configuration         = job_configuration
        self.job_repository            = job_repository
        self.job_message_repository    = job_message_repository
        self.job_event_repository      = job_event_repository
        self.job_chunk_repository      = job_chunk_repository
        self.job_task_repository       = job_task_repository
        self.chat_thread_repository    = chat_thread_repository
        self.thread_message_repository = thread_message_repository

    async def _publish_terminal_async(self, run_id : uuid.UUID, job_status : JobStatus, error_message : Optional[str], usage_dictionary : Optional[Dict[str, Any]], message_count : int, event_count : int, last_sequence_number : int) -> None:
        meta_key   = RedisKeyBuilder.get_job_meta_key(str(run_id))
        stream_key = RedisKeyBuilder.get_job_stream_key(str(run_id))
        try:
            completed_at          = datetime.now(timezone.utc).isoformat()
            meta_field_dictionary = {
                "status"        : job_status.value,
                "error_message" : error_message or "",
                "usage"         : json.dumps(usage_dictionary, ensure_ascii = False) if usage_dictionary is not None else "",
                "message_count" : str(message_count),
                "event_count"   : str(event_count),
                "last_seq"      : str(last_sequence_number),
                "completed_at"  : completed_at,
                "updated_at"    : completed_at
            }
            end_data_dictionary = {
                "status"        : job_status.value,
                "error_message" : error_message,
                "usage"         : usage_dictionary,
                "message_count" : message_count,
                "event_count"   : event_count
            }
            end_field_dictionary = {
                "seq"        : str(last_sequence_number),
                "chunk_type" : "__end__",
                "ns"         : "[]",
                "data"       : json.dumps(end_data_dictionary, ensure_ascii = False),
                "created_at" : completed_at
            }
            await self.redis_stream_client.finalize_stream_async(
                meta_key,
                stream_key,
                meta_field_dictionary,
                end_field_dictionary,
                self.job_configuration.redis_stream_maximum_length,
                self.job_configuration.redis_grace_ttl_second_count
            )
        except RedisError:
            # reaper가 heartbeat 만료 meta를 다시 발견하면 PostgreSQL terminal 상태로 재발행한다
            pass

    @staticmethod
    def _get_preview_from_message_list(merged_message_dictionary_list : List[Dict[str, Any]]) -> Optional[str]:
        for merged_message_dictionary in reversed(merged_message_dictionary_list):
            if merged_message_dictionary.get("role") == "ai" and merged_message_dictionary.get("ns_path") == "":
                content_value = merged_message_dictionary.get("content")
                return content_value[:200] if isinstance(content_value, str) else str(content_value)[:200]
        return None

    async def transfer_async(self, run_id : uuid.UUID, thread_id : uuid.UUID, job_status : JobStatus, error_message : Optional[str], usage_dictionary : Optional[Dict[str, Any]], merged_message_dictionary_list : List[Dict[str, Any]]) -> bool:
        is_updated           = False
        message_count        = 0
        event_count          = 0
        chunk_count          = 0
        task_count           = 0
        last_sequence_number = 0
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            async with connection.transaction():
                is_active      = await self.job_repository.lock_job_for_transfer_async(connection, run_id)
                job_dictionary = await connection.fetchrow("SELECT user_id, turn_number FROM llm_job WHERE run_id = $1", run_id)
                if is_active:
                    for merged_message_dictionary in merged_message_dictionary_list:
                        await self.job_message_repository.insert_message_async(
                            self.uuid_v7_generator.generate(),
                            run_id,
                            thread_id,
                            merged_message_dictionary,
                            connection
                        )
                        if merged_message_dictionary.get("role") == "ai" and merged_message_dictionary.get("ns_path") == "":
                            await self.thread_message_repository.upsert_assistant_message_async(
                                self.uuid_v7_generator.generate(),
                                thread_id,
                                run_id,
                                int(job_dictionary["turn_number"]) if job_dictionary is not None else 1,
                                1000,
                                merged_message_dictionary,
                                connection
                            )
                    await self.job_task_repository.mark_unfinished_task_list_async(run_id, job_status.value, connection)
                last_sequence_number         = await self.job_chunk_repository.get_last_sequence_number_async(run_id, connection)
                stored_usage_dictionary_list = await self.job_message_repository.get_usage_dictionary_list_async(run_id, connection)
                if usage_dictionary is None:
                    usage_dictionary = UsageAccumulator.get_usage_dictionary(stored_usage_dictionary_list)
                if is_active:
                    message_count = await self.job_message_repository.get_message_count_async(run_id, connection)
                    event_count   = await self.job_event_repository.get_event_count_async(run_id, connection)
                    chunk_count   = await self.job_chunk_repository.get_chunk_count_async(run_id, connection)
                    task_count    = await self.job_task_repository.get_task_count_async(run_id, connection)
                    is_updated    = await self.job_repository.update_job_finished_async(
                        run_id,
                        job_status.value,
                        error_message,
                        usage_dictionary,
                        message_count,
                        event_count,
                        last_sequence_number,
                        chunk_count,
                        task_count,
                        connection
                    )
                    if job_dictionary is not None:
                        await self.chat_thread_repository.update_thread_on_finish_async(
                            thread_id,
                            job_dictionary["user_id"],
                            run_id,
                            job_status.value,
                            JobTransfer._get_preview_from_message_list(merged_message_dictionary_list),
                            connection
                        )
        if not is_updated:
            terminal_job_dictionary = await self.job_repository.get_job_async(run_id)
            if terminal_job_dictionary is None or terminal_job_dictionary["status"] not in {JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
                return False
            job_status           = JobStatus(terminal_job_dictionary["status"])
            error_message        = terminal_job_dictionary.get("error_message")
            usage_value          = terminal_job_dictionary.get("usage")
            usage_dictionary     = usage_value if isinstance(usage_value, dict) else None
            message_count        = int(terminal_job_dictionary.get("message_count") or 0)
            event_count          = int(terminal_job_dictionary.get("event_count") or 0)
            last_sequence_number = int(terminal_job_dictionary.get("last_sequence_number") or last_sequence_number)
        await self._publish_terminal_async(
            run_id,
            job_status,
            error_message,
            usage_dictionary,
            message_count,
            event_count,
            last_sequence_number
        )
        return is_updated
