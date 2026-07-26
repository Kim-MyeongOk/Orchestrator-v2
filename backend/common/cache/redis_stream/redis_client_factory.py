import redis.asyncio as redis_asyncio

from redis.asyncio.retry import Retry
from redis.backoff       import NoBackoff

from common.cache.redis_stream.redis_configuration import RedisConfiguration

##################################################
# Redis 클라이언트 팩토리
# RedisConfiguration 으로부터 단일 노드용 redis.asyncio.Redis 클라이언트를 생성한다.
# (클러스터 모드는 RedisCluster 를 별도로 사용하므로 여기서 다루지 않는다)
##################################################
class RedisClientFactory:
    @staticmethod
    def create_client(redis_configuration : RedisConfiguration, decode_responses : bool = True) -> redis_asyncio.Redis:
        return redis_asyncio.Redis(
            host                   = redis_configuration.host,
            port                   = redis_configuration.port,
            password               = redis_configuration.password,
            db                     = redis_configuration.database_index,
            socket_timeout         = redis_configuration.socket_timeout_second_count,
            socket_connect_timeout = redis_configuration.socket_connect_timeout_second_count,
            retry                  = Retry(NoBackoff(), redis_configuration.command_maximum_retry_count),
            decode_responses       = decode_responses
        )
