import asyncio
import uuid

from typing             import Optional
from typing             import Dict
from typing             import Any
from datetime           import datetime
from datetime           import timedelta
from datetime           import timezone
from asyncpg.exceptions import PostgresError
from redis.exceptions   import RedisError

from common.cache.redis_stream.redis_stream_client import RedisStreamClient
from app.llm.job.job_configuration                 import JobConfiguration
from app.llm.job.job_transfer.job_transfer         import JobTransfer
from app.llm.repository.job_repository             import JobRepository
from app.llm.job.job_manager.job_status            import JobStatus
from common.cache.redis_stream.redis_key_builder   import RedisKeyBuilder

class JobReaper:
    def __init__(self, redis_stream_client : RedisStreamClient, job_configuration : JobConfiguration, job_transfer : JobTransfer, job_repository : JobRepository) -> None:
        self.redis_stream_client = redis_stream_client
        self.job_configuration   = job_configuration
        self.job_transfer        = job_transfer
        self.job_repository      = job_repository
        self._reaper_task        : Optional[asyncio.Task[None]] = None

    @staticmethod
    def _is_valid_active_meta(meta_dictionary : Dict[str, str], job_dictionary : Dict[str, Any]) -> bool:
        if meta_dictionary.get("status") not in {JobStatus.PENDING.value, JobStatus.RUNNING.value}:
            return False
        if meta_dictionary.get("run_id") != str(job_dictionary.get("run_id")):
            return False
        if meta_dictionary.get("thread_id") != str(job_dictionary.get("thread_id")):
            return False
        if meta_dictionary.get("user_id") != str(job_dictionary.get("user_id")):
            return False
        heartbeat_at_text = meta_dictionary.get("heartbeat_at")
        if heartbeat_at_text is None:
            return False
        try:
            heartbeat_at = datetime.fromisoformat(heartbeat_at_text)
        except ValueError:
            return False
        return heartbeat_at.tzinfo is not None

    async def _reap_job_async(self, meta_key : str, current_time : datetime) -> None:
        meta_dictionary = await self.redis_stream_client.get_hash_dictionary_async(meta_key)
        if meta_dictionary.get("status") not in {JobStatus.PENDING.value, JobStatus.RUNNING.value}:
            return
        heartbeat_at_text = meta_dictionary.get("heartbeat_at")
        if heartbeat_at_text is None:
            return
        heartbeat_at = datetime.fromisoformat(heartbeat_at_text)
        if heartbeat_at.tzinfo is None:
            raise ValueError(f"HEARTBEAT TIMEZONE IS REQUIRED : {heartbeat_at_text}")
        elapsed_second_count = (current_time - heartbeat_at).total_seconds()
        if elapsed_second_count <= self.job_configuration.heartbeat_expire_second_count:
            return
        run_id    = uuid.UUID(RedisKeyBuilder.extract_run_id_from_key(meta_key))
        thread_id = uuid.UUID(meta_dictionary["thread_id"])
        await self.redis_stream_client.set_hash_dictionary_async(
            meta_key,
            {
                "cancel_requested" : "1",
                "cancel_reason"    : "heartbeat_expired"
            }
        )
        fenced_meta_dictionary = await self.redis_stream_client.get_hash_dictionary_async(meta_key)
        await self.job_transfer.transfer_async(
            run_id,
            uuid.UUID(fenced_meta_dictionary.get("thread_id") or str(thread_id)),
            JobStatus.FAILED,
            "HEARTBEAT EXPIRED",
            None,
            []
        )

    async def _reap_active_gap_async(self, current_time : datetime) -> None:
        stale_before               = current_time - timedelta(seconds = self.job_configuration.heartbeat_expire_second_count)
        active_job_dictionary_list = await self.job_repository.get_stale_active_job_list_async(stale_before)
        for active_job_dictionary in active_job_dictionary_list:
            run_id = uuid.UUID(active_job_dictionary["run_id"])
            meta_dictionary = await self.redis_stream_client.get_hash_dictionary_async(RedisKeyBuilder.get_job_meta_key(str(run_id)))
            if JobReaper._is_valid_active_meta(meta_dictionary, active_job_dictionary):
                continue
            await self.job_transfer.transfer_async(
                run_id,
                uuid.UUID(active_job_dictionary["thread_id"]),
                JobStatus.FAILED,
                "HEARTBEAT EXPIRED",
                None,
                []
            )

    async def reap_once_async(self) -> None:
        meta_key_list = await self.redis_stream_client.scan_key_list_async("job:*:meta")
        current_time  = datetime.now(timezone.utc)
        for meta_key in meta_key_list:
            try:
                await self._reap_job_async(meta_key, current_time)
            except (PostgresError, RedisError, ValueError, KeyError, IndexError):
                continue
        await self._reap_active_gap_async(current_time)

    async def _run_async(self) -> None:
        while True:
            try:
                await self.reap_once_async()
            except (PostgresError, RedisError, ValueError, KeyError, IndexError):
                pass
            await asyncio.sleep(self.job_configuration.heartbeat_interval_second_count)

    async def start_async(self) -> None:
        if self._reaper_task is None:
            self._reaper_task = asyncio.create_task(self._run_async(), name = "llm-job-reaper")

    async def stop_async(self) -> None:
        if self._reaper_task is not None:
            self._reaper_task.cancel()
            try:
                await self._reaper_task
            except asyncio.CancelledError:
                pass
            self._reaper_task = None
