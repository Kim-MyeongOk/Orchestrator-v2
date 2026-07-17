import redis.asyncio as redis_asyncio

from typing                import Optional
from typing                import Union
from redis.asyncio.cluster import RedisCluster
from redis.asyncio.retry   import Retry
from redis.backoff         import NoBackoff
from typing                import Dict
from typing                import List
from typing                import Tuple

from common.cache.redis_stream.redis_configuration import RedisConfiguration

class RedisStreamClient:
    ADD_ACTIVE_JOB_STREAM_SCRIPT = """
local status = redis.call("hget", KEYS[1], "status")
local cancel_requested = redis.call("hget", KEYS[1], "cancel_requested")
if (status ~= "pending" and status ~= "running") or cancel_requested == "1" then
    return false
end
local entry_id = redis.call(
    "xadd", KEYS[2], "MAXLEN", "~", ARGV[6], "*",
    "seq", ARGV[1], "chunk_type", ARGV[2], "ns", ARGV[3],
    "data", ARGV[4], "created_at", ARGV[5]
)
redis.call("expire", KEYS[2], ARGV[7])
redis.call(
    "hset", KEYS[1],
    "last_seq", ARGV[1], "heartbeat_at", ARGV[5], "updated_at", ARGV[5]
)
return entry_id
    """
    START_JOB_SCRIPT = """
local status = redis.call("hget", KEYS[1], "status")
local cancel_requested = redis.call("hget", KEYS[1], "cancel_requested")
if status ~= "pending" or cancel_requested == "1" then
    return false
end
redis.call(
    "hset", KEYS[1], "status", "running", "started_at", ARGV[1],
    "heartbeat_at", ARGV[1], "updated_at", ARGV[1]
)
return true
    """
    REQUEST_JOB_CANCELLATION_SCRIPT = """
if redis.call("exists", KEYS[1]) == 0 then
    return false
end
local status = redis.call("hget", KEYS[1], "status")
if status ~= "pending" and status ~= "running" then
    return false
end
redis.call(
    "hset", KEYS[1], "cancel_requested", "1", "cancel_reason", ARGV[1], "updated_at", ARGV[2]
)
return true
    """
    HEARTBEAT_JOB_SCRIPT = """
local status = redis.call("hget", KEYS[1], "status")
local cancel_requested = redis.call("hget", KEYS[1], "cancel_requested")
if cancel_requested == "1" then
    return {0, redis.call("hget", KEYS[1], "cancel_reason") or "cancelled"}
end
if status ~= "pending" and status ~= "running" then
    return {0, "heartbeat_expired"}
end
redis.call("hset", KEYS[1], "heartbeat_at", ARGV[1], "updated_at", ARGV[1])
return {1, ""}
    """
    FINALIZE_JOB_STREAM_SCRIPT = """
local status = redis.call("hget", KEYS[1], "status")
if status == "completed" or status == "failed" or status == "cancelled" then
    redis.call("expire", KEYS[1], ARGV[11])
    redis.call("expire", KEYS[2], ARGV[11])
    return false
end
local current_last_sequence_number = tonumber(redis.call("hget", KEYS[1], "last_seq")) or 0
local requested_last_sequence_number = tonumber(ARGV[7]) or 0
local end_sequence_number = math.max(current_last_sequence_number, requested_last_sequence_number) + 1
redis.call(
    "hset", KEYS[1],
    "status", ARGV[1], "error_message", ARGV[2], "usage", ARGV[3],
    "message_count", ARGV[4], "event_count", ARGV[5],
    "last_seq", tostring(end_sequence_number), "completed_at", ARGV[6], "updated_at", ARGV[6]
)
local entry_id = redis.call(
    "xadd", KEYS[2], "MAXLEN", "~", ARGV[10], "*",
    "seq", tostring(end_sequence_number), "chunk_type", "__end__", "ns", ARGV[8],
    "data", ARGV[9], "created_at", ARGV[6]
)
redis.call("expire", KEYS[1], ARGV[11])
redis.call("expire", KEYS[2], ARGV[11])
return entry_id
    """
    RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
    """

    def __init__(self, redis_configuration : RedisConfiguration) -> None:
        self.redis_configuration                                               = redis_configuration
        self.redis_client : Optional[Union[redis_asyncio.Redis, RedisCluster]] = None

    def _get_redis_client(self) -> Union[redis_asyncio.Redis, RedisCluster]:
        if self.redis_client is None:
            raise ValueError("REDIS CLIENT NOT OPENED : redis_client")
        return self.redis_client

    async def open_async(self) -> None:
        if self.redis_client is not None:
            return
        if self.redis_configuration.is_cluster:
            self.redis_client = RedisCluster(
                host                         = self.redis_configuration.host,
                port                         = self.redis_configuration.port,
                password                     = self.redis_configuration.password,
                socket_timeout               = self.redis_configuration.socket_timeout_second_count,
                socket_connect_timeout       = self.redis_configuration.socket_connect_timeout_second_count,
                cluster_error_retry_attempts = self.redis_configuration.command_maximum_retry_count,
                retry                        = Retry(NoBackoff(), self.redis_configuration.command_maximum_retry_count),
                decode_responses             = True
            )
        else:
            self.redis_client = redis_asyncio.Redis(
                host                   = self.redis_configuration.host,
                port                   = self.redis_configuration.port,
                password               = self.redis_configuration.password,
                db                     = self.redis_configuration.database_index,
                socket_timeout         = self.redis_configuration.socket_timeout_second_count,
                socket_connect_timeout = self.redis_configuration.socket_connect_timeout_second_count,
                retry                  = Retry(NoBackoff(), self.redis_configuration.command_maximum_retry_count),
                decode_responses       = True
            )

    async def ping_async(self) -> bool:
        return bool(await self._get_redis_client().ping())

    async def start_job_if_pending_async(self, meta_key : str, started_at : str) -> bool:
        is_started = await self._get_redis_client().eval(RedisStreamClient.START_JOB_SCRIPT, 1, meta_key, started_at)
        return bool(is_started)

    async def request_job_cancellation_async(self, meta_key : str, cancellation_reason : str, updated_at : str) -> bool:
        is_updated = await self._get_redis_client().eval(RedisStreamClient.REQUEST_JOB_CANCELLATION_SCRIPT, 1, meta_key, cancellation_reason, updated_at)
        return bool(is_updated)

    async def heartbeat_job_async(self, meta_key : str, heartbeat_at : str) -> Optional[str]:
        result_list = await self._get_redis_client().eval(RedisStreamClient.HEARTBEAT_JOB_SCRIPT, 1, meta_key, heartbeat_at)
        if int(result_list[0]) == 1:
            return None
        return str(result_list[1] or "heartbeat_expired")

    ##################################################
    # 스트림
    ##################################################

    async def add_stream_entry_async(self, stream_key : str, field_dictionary : Dict[str, str], maximum_length : int) -> str:
        return await self._get_redis_client().xadd(stream_key, field_dictionary, maxlen = maximum_length, approximate = True)

    async def add_stream_entry_with_expire_async(self, stream_key : str, field_dictionary : Dict[str, str], maximum_length : int, ttl_second_count : int) -> str:
        async with self._get_redis_client().pipeline(transaction = True) as pipeline:
            pipeline.xadd(stream_key, field_dictionary, maxlen = maximum_length, approximate = True)
            pipeline.expire(stream_key, ttl_second_count)
            result_list = await pipeline.execute()
            return str(result_list[0])

    async def add_active_job_stream_entry_async(self, meta_key : str, stream_key : str, field_dictionary : Dict[str, str], maximum_length : int, ttl_second_count : int) -> Optional[str]:
        entry_id = await self._get_redis_client().eval(
            RedisStreamClient.ADD_ACTIVE_JOB_STREAM_SCRIPT,
            2,
            meta_key,
            stream_key,
            field_dictionary["seq"],
            field_dictionary["chunk_type"],
            field_dictionary["ns"],
            field_dictionary["data"],
            field_dictionary["created_at"],
            str(maximum_length),
            str(ttl_second_count)
        )
        return str(entry_id) if entry_id not in (None, False) else None

    async def finalize_stream_async(self, meta_key : str, stream_key : str, meta_field_dictionary : Dict[str, str], end_field_dictionary : Dict[str, str], maximum_length : int, ttl_second_count : int) -> Optional[str]:
        entry_id = await self._get_redis_client().eval(
            RedisStreamClient.FINALIZE_JOB_STREAM_SCRIPT,
            2,
            meta_key,
            stream_key,
            meta_field_dictionary["status"],
            meta_field_dictionary["error_message"],
            meta_field_dictionary["usage"],
            meta_field_dictionary["message_count"],
            meta_field_dictionary["event_count"],
            meta_field_dictionary["completed_at"],
            meta_field_dictionary["last_seq"],
            end_field_dictionary["ns"],
            end_field_dictionary["data"],
            str(maximum_length),
            str(ttl_second_count)
        )
        return str(entry_id) if entry_id not in (None, False) else None

    async def read_stream_async(self, stream_key : str, last_entry_id : str, block_millisecond_count : int) -> List[Tuple[str, Dict[str, str]]]:
        response_list = await self._get_redis_client().xread({stream_key : last_entry_id}, block = block_millisecond_count)
        if not response_list:
            return []
        entry_list = []
        for _stream_name, stream_entry_list in response_list:
            for entry_id, field_dictionary in stream_entry_list:
                entry_list.append((entry_id, field_dictionary))
        return entry_list

    ##################################################
    # 해시
    ##################################################

    async def set_hash_dictionary_async(self, hash_key : str, field_dictionary : Dict[str, str]) -> None:
        await self._get_redis_client().hset(hash_key, mapping = field_dictionary)

    async def set_hash_dictionary_with_expire_async(self, hash_key : str, field_dictionary : Dict[str, str], ttl_second_count : int) -> None:
        async with self._get_redis_client().pipeline(transaction = True) as pipeline:
            pipeline.hset(hash_key, mapping = field_dictionary)
            pipeline.expire(hash_key, ttl_second_count)
            await pipeline.execute()

    async def get_hash_dictionary_async(self, hash_key : str) -> Dict[str, str]:
        return await self._get_redis_client().hgetall(hash_key)

    async def set_hash_field_async(self, hash_key : str, field_name : str, field_value : str) -> None:
        await self._get_redis_client().hset(hash_key, field_name, field_value)

    ##################################################
    # 키 / TTL / 락
    ##################################################

    async def is_key_exists_async(self, target_key : str) -> bool:
        return bool(await self._get_redis_client().exists(target_key))

    async def set_expire_async(self, target_key : str, ttl_second_count : int) -> None:
        await self._get_redis_client().expire(target_key, ttl_second_count)

    async def acquire_lock_async(self, lock_key : str, lock_value : str, ttl_second_count : int) -> bool:
        return bool(await self._get_redis_client().set(lock_key, lock_value, nx = True, ex = ttl_second_count))

    async def release_lock_async(self, lock_key : str, lock_value : str) -> bool:
        deleted_count = await self._get_redis_client().eval(RedisStreamClient.RELEASE_LOCK_SCRIPT, 1, lock_key, lock_value)
        return bool(deleted_count)

    async def get_string_async(self, target_key : str) -> Optional[str]:
        return await self._get_redis_client().get(target_key)

    async def scan_key_list_async(self, match_pattern : str) -> List[str]:
        key_list = []
        async for scanned_key in self._get_redis_client().scan_iter(match = match_pattern):
            key_list.append(scanned_key)
        return key_list

    async def delete_key_async(self, target_key : str) -> None:
        await self._get_redis_client().delete(target_key)

    async def close_async(self) -> None:
        if self.redis_client is not None:
            await self.redis_client.aclose()
            self.redis_client = None
