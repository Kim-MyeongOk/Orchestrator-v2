import uuid
import json
import asyncio
import time

from typing           import Dict
from typing           import Any
from typing           import List
from typing           import Optional
from redis.exceptions import RedisError
from typing           import Callable

from common.cache.redis_stream.redis_stream_client           import RedisStreamClient
from common.identifier.uuid_v7.uuid_v7_generator             import UUIDV7Generator
from app.llm.job.job_configuration                           import JobConfiguration
from app.llm.repository.job_repository                       import JobRepository
from app.llm.repository.job_message_repository               import JobMessageRepository
from app.llm.repository.job_event_repository                 import JobEventRepository
from app.llm.repository.job_chunk_repository                 import JobChunkRepository
from app.llm.repository.job_task_repository                  import JobTaskRepository
from app.llm.job.job_transfer.job_transfer                   import JobTransfer
from app.llm.stream_pipeline.normalized_chunk                import NormalizedChunk
from common.cache.redis_stream.redis_key_builder             import RedisKeyBuilder
from app.llm.stream_pipeline.message_accumulator             import MessageAccumulator
from app.llm.stream_pipeline.task_projector                  import TaskProjector
from app.llm.job.job_manager.job_status                      import JobStatus
from app.llm.stream_pipeline.chunk_normalizer                import ChunkNormalizer
from app.llm.stream_pipeline.chunk_task_correlation_resolver import ChunkTaskCorrelationResolver
from app.llm.agent.model_configuration                       import ModelConfiguration
from app.llm.agent.deep_agent_factory                        import DeepAgentFactory
from app.llm.stream_pipeline.usage_accumulator               import UsageAccumulator

class JobExecutor:
    def __init__(self, redis_stream_client : RedisStreamClient, uuid_v7_generator : UUIDV7Generator, job_configuration : JobConfiguration, job_repository : JobRepository, job_message_repository : JobMessageRepository, job_event_repository : JobEventRepository, job_chunk_repository : JobChunkRepository, job_task_repository : JobTaskRepository, job_transfer : JobTransfer) -> None:
        self.redis_stream_client    = redis_stream_client
        self.uuid_v7_generator      = uuid_v7_generator
        self.job_configuration      = job_configuration
        self.job_repository         = job_repository
        self.job_message_repository = job_message_repository
        self.job_event_repository   = job_event_repository
        self.job_chunk_repository   = job_chunk_repository
        self.job_task_repository    = job_task_repository
        self.job_transfer           = job_transfer

    async def _build_input_message_list_async(self, user_id : uuid.UUID, thread_id : uuid.UUID, request_payload_dictionary : Dict[str, Any]) -> List[Dict[str, Any]]:
        input_message_dictionary_list : List[Dict[str, Any]] = []
        thread_job_dictionary_list                           = await self.job_repository.get_thread_job_list_async(thread_id, user_id)
        for thread_job_dictionary in thread_job_dictionary_list:
            historical_request_payload_dictionary = thread_job_dictionary.get("request_payload") or {}
            historical_message_dictionary_list    = historical_request_payload_dictionary.get("messages") or []
            input_message_dictionary_list.extend(historical_message_dictionary_list)
            assistant_message_dictionary = await self.job_message_repository.get_last_assistant_message_async(uuid.UUID(thread_job_dictionary["run_id"]))
            if assistant_message_dictionary is not None:
                input_message_dictionary_list.append(
                    {
                        "role"    : "assistant",
                        "content" : assistant_message_dictionary.get("content")
                    }
                )
        input_message_dictionary_list.extend(request_payload_dictionary.get("messages") or [])
        return input_message_dictionary_list

    async def _publish_chunk_async(self, run_id : uuid.UUID, normalized_chunk : NormalizedChunk) -> bool:
        run_id_string = str(run_id)
        stream_key    = RedisKeyBuilder.get_job_stream_key(run_id_string)
        meta_key      = RedisKeyBuilder.get_job_meta_key(run_id_string)
        field_dictionary = {
            "seq"            : str(normalized_chunk.sequence),
            "chunk_type"     : normalized_chunk.chunk_type,
            "ns"             : json.dumps(normalized_chunk.namespace_list, ensure_ascii = False),
            "task_id"        : normalized_chunk.task_id or "",
            "parent_task_id" : normalized_chunk.parent_task_id or "",
            "task_link_type" : normalized_chunk.task_link_type or "",
            "data"           : json.dumps(normalized_chunk.data_dictionary, ensure_ascii = False),
            "created_at"     : normalized_chunk.created_at
        }
        entry_id = await self.redis_stream_client.add_active_job_stream_entry_async(
            meta_key,
            stream_key,
            field_dictionary,
            self.job_configuration.redis_stream_maximum_length,
            self.job_configuration.redis_safety_ttl_second_count
        )
        return entry_id is not None

    @staticmethod
    def _buffer_chunk(normalized_chunk : NormalizedChunk, message_accumulator : MessageAccumulator, pending_flush_dictionary : Dict[str, List[Any]]) -> None:
        # 일괄 flush 전까지 메모리에 누적한다 (DB 쓰기는 종료 시점 JobTransfer 가 한 트랜잭션으로 수행)
        pending_flush_dictionary["chunk_list"].append(normalized_chunk)
        task_projection_dictionary = TaskProjector.create_task_projection_dictionary(normalized_chunk)
        if task_projection_dictionary is not None:
            pending_flush_dictionary["task_projection_list"].append(task_projection_dictionary)
        if normalized_chunk.chunk_type == "messages":
            merged_message_dictionary = message_accumulator.accumulate(normalized_chunk)
            if merged_message_dictionary is not None:
                pending_flush_dictionary["streamed_message_list"].append(merged_message_dictionary)
        elif normalized_chunk.chunk_type in {"tasks", "custom"}:
            pending_flush_dictionary["event_chunk_list"].append(normalized_chunk)

    async def _get_distributed_cancellation_reason_async(self, run_id : uuid.UUID) -> Optional[str]:
        meta_dictionary = await self.redis_stream_client.get_hash_dictionary_async(RedisKeyBuilder.get_job_meta_key(str(run_id)))
        if not meta_dictionary:
            return "heartbeat_expired"
        if meta_dictionary.get("cancel_requested") == "1":
            return meta_dictionary.get("cancel_reason") or "cancelled"
        if meta_dictionary.get("status") not in {JobStatus.PENDING.value, JobStatus.RUNNING.value}:
            return meta_dictionary.get("cancel_reason") or "heartbeat_expired"
        return None

    async def _process_chunk_async(self, run_id : uuid.UUID, thread_id : uuid.UUID, normalized_chunk : NormalizedChunk, message_accumulator : MessageAccumulator, cancellation_reason_dictionary : Dict[str, str], pending_flush_dictionary : Dict[str, List[Any]]) -> None:
        # 실행 중에는 Redis 로만 발행하고(실시간 구독), DB 적재는 종료 시점에 일괄로 수행한다.
        # 따라서 프로세스가 flush 전에 죽으면 청크는 유실되고 reaper 가 실패 상태만 DB 에 남긴다.
        JobExecutor._buffer_chunk(normalized_chunk, message_accumulator, pending_flush_dictionary)
        is_published = await self._publish_chunk_async(run_id, normalized_chunk)
        if not is_published:
            cancellation_reason_dictionary["reason"] = await self._get_distributed_cancellation_reason_async(run_id) or "cancelled"
            raise asyncio.CancelledError()

    async def _heartbeat_async(self, run_id : uuid.UUID, execution_task : asyncio.Task[Any], cancellation_reason_dictionary : Dict[str, str]) -> None:
        meta_key                            = RedisKeyBuilder.get_job_meta_key(str(run_id))
        last_success_monotonic_second_count = time.monotonic()
        while True:
            await asyncio.sleep(self.job_configuration.heartbeat_interval_second_count)
            try:
                current_time        = ChunkNormalizer.get_current_time_string()
                cancellation_reason = await self.redis_stream_client.heartbeat_job_async(meta_key, current_time)
                if cancellation_reason is not None:
                    cancellation_reason_dictionary["reason"] = cancellation_reason
                    execution_task.cancel()
                    return
                last_success_monotonic_second_count = time.monotonic()
            except RedisError:
                elapsed_second_count = time.monotonic() - last_success_monotonic_second_count
                if elapsed_second_count >= self.job_configuration.heartbeat_expire_second_count:
                    cancellation_reason_dictionary["reason"] = "heartbeat_expired"
                    execution_task.cancel()
                    return

    async def execute_async(self, run_id : uuid.UUID, thread_id : uuid.UUID, user_id : uuid.UUID, request_payload_dictionary : Dict[str, Any], model_configuration : ModelConfiguration, cancellation_reason_callable : Callable[[], Optional[str]]) -> None:
        chunk_normalizer                                              = ChunkNormalizer()
        chunk_task_correlation_resolver                               = ChunkTaskCorrelationResolver()
        message_accumulator                                           = MessageAccumulator()
        heartbeat_task                 : Optional[asyncio.Task[None]] = None
        cancellation_reason_dictionary : Dict[str, str]               = {}
        job_status                                                    = JobStatus.COMPLETED
        error_message                  : Optional[str]                = None
        # 일괄 flush 버퍼 : 실행 중 누적했다가 종료 시 JobTransfer 가 한 트랜잭션으로 적재한다
        pending_flush_dictionary : Dict[str, List[Any]] = {
            "chunk_list"            : [],
            "event_chunk_list"      : [],
            "task_projection_list"  : [],
            "streamed_message_list" : []
        }
        try:
            async with asyncio.timeout(self.job_configuration.execution_timeout_second_count):
                is_running = await self.job_repository.update_job_running_async(run_id)
                if not is_running:
                    return
                started_at       = ChunkNormalizer.get_current_time_string()
                is_redis_running = await self.redis_stream_client.start_job_if_pending_async(RedisKeyBuilder.get_job_meta_key(str(run_id)), started_at)
                if not is_redis_running:
                    cancellation_reason_dictionary["reason"] = await self._get_distributed_cancellation_reason_async(run_id) or "cancelled"
                    raise asyncio.CancelledError()
                execution_task = asyncio.current_task()
                if execution_task is None:
                    raise RuntimeError("EXECUTION TASK NOT FOUND")
                heartbeat_task                = asyncio.create_task(self._heartbeat_async(run_id, execution_task, cancellation_reason_dictionary), name = f"llm-job-heartbeat-{run_id}")
                input_message_dictionary_list = await self._build_input_message_list_async(user_id, thread_id, request_payload_dictionary)
                deep_agent                    = DeepAgentFactory.create(model_configuration)
                runnable_configuration        = {
                    "run_id"       : run_id,
                    "configurable" : {"thread_id" : str(thread_id)}
                }
                async for stream_chunk in deep_agent.astream({"messages" : input_message_dictionary_list}, runnable_configuration, stream_mode = ["tasks", "messages", "custom"], subgraphs = True, version = "v2"):
                    normalized_chunk = chunk_normalizer.normalize(stream_chunk)
                    if normalized_chunk is None:
                        continue
                    normalized_chunk = chunk_task_correlation_resolver.resolve(normalized_chunk)
                    await self._process_chunk_async(run_id, thread_id, normalized_chunk, message_accumulator, cancellation_reason_dictionary, pending_flush_dictionary)
        except TimeoutError:
            job_status    = JobStatus.FAILED
            error_message = f"EXECUTION TIMEOUT : {self.job_configuration.execution_timeout_second_count}s"
        except asyncio.CancelledError:
            cancellation_reason = cancellation_reason_dictionary.get("reason") or cancellation_reason_callable()
            if cancellation_reason == "cancelled":
                job_status = JobStatus.CANCELLED
            elif cancellation_reason == "client_disconnected":
                job_status    = JobStatus.FAILED
                error_message = "CLIENT DISCONNECTED"
            elif cancellation_reason == "heartbeat_expired":
                job_status    = JobStatus.FAILED
                error_message = "HEARTBEAT EXPIRED"
            else:
                job_status    = JobStatus.FAILED
                error_message = "EXECUTION CANCELLED"
        except Exception as exception:
            job_status    = JobStatus.FAILED
            error_message = str(exception) or exception.__class__.__name__
        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            # 스트리밍 중 확정된 메시지 + 종료 시 남은 잔여 메시지를 합쳐 최종 메시지 목록을 만든다
            merged_message_dictionary_list = pending_flush_dictionary["streamed_message_list"] + message_accumulator.flush_all()
            usage_dictionary_list          = [merged_message_dictionary["usage"] for merged_message_dictionary in merged_message_dictionary_list if isinstance(merged_message_dictionary.get("usage"), dict)]
            usage_dictionary               = UsageAccumulator.get_usage_dictionary(usage_dictionary_list)
            await asyncio.shield(
                self.job_transfer.transfer_async(
                    run_id,
                    thread_id,
                    job_status,
                    error_message,
                    usage_dictionary,
                    merged_message_dictionary_list,
                    pending_flush_dictionary["chunk_list"],
                    pending_flush_dictionary["event_chunk_list"],
                    pending_flush_dictionary["task_projection_list"]
                )
            )
