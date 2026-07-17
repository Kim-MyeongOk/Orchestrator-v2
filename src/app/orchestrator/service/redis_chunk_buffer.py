##################################################
# Redis 청크 버퍼
# 스트리밍 중 발생하는 청크를 (thread_id, run_id) 단위 List 에 실시간 누적(Append)하고,
# flush 시점에 전체를 반환/삭제한다. TTL 로 flush 실패 잔존 데이터를 자동 정리한다.
##################################################

import json

# uv add redis
from typing        import Any
from typing        import Dict
from typing        import List
from redis.asyncio import Redis


class RedisChunkBuffer:
    def __init__(self, redis_client : Redis, buffer_ttl_second_count : int = 3600):
        self.redis_client            = redis_client
        self.buffer_ttl_second_count = buffer_ttl_second_count  # 버퍼 TTL(초) (기본값 : 3600)

    @staticmethod
    def _create_chunk_list_key(thread_id : str, run_id : str) -> str:
        # {thread_id} 해시태그 : Redis Cluster 에서 같은 스레드의 키가 동일 슬롯에 놓이게 한다
        return f"orch:{{{thread_id}}}:run:{run_id}:chunk_list"

    async def append_chunk_async(self, thread_id : str, run_id : str, chunk_dictionary : Dict[str, Any]) -> None:
        chunk_list_key = RedisChunkBuffer._create_chunk_list_key(thread_id, run_id)
        chunk_json     = json.dumps(chunk_dictionary, ensure_ascii = False, default = str)
        async with self.redis_client.pipeline(transaction = False) as redis_pipeline:
            redis_pipeline.rpush(chunk_list_key, chunk_json)
            redis_pipeline.expire(chunk_list_key, self.buffer_ttl_second_count)
            await redis_pipeline.execute()

    async def get_chunk_dictionary_list_async(self, thread_id : str, run_id : str) -> List[Dict[str, Any]]:
        chunk_list_key  = RedisChunkBuffer._create_chunk_list_key(thread_id, run_id)
        chunk_json_list = await self.redis_client.lrange(chunk_list_key, 0, -1)
        return [json.loads(chunk_json) for chunk_json in chunk_json_list]

    async def delete_buffer_async(self, thread_id : str, run_id : str) -> None:
        await self.redis_client.delete(RedisChunkBuffer._create_chunk_list_key(thread_id, run_id))
