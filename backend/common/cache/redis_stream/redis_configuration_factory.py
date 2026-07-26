import os

from common.cache.redis_stream.redis_configuration import RedisConfiguration
from common.config.environment_variable_helper     import EnvironmentVariableHelper

##################################################
# Redis 설정 팩토리
# REDIS_* 환경변수로부터 RedisConfiguration 을 구성한다.
# 메인 서버와 모니터 앱이 동일한 접속 설정(비밀번호/타임아웃/재시도)을 공유하게 한다.
##################################################
class RedisConfigurationFactory:
    @staticmethod
    def create_from_environment() -> RedisConfiguration:
        redis_password = os.getenv("REDIS_PASSWORD")
        return RedisConfiguration(
            host                                = os.getenv("REDIS_HOST", "localhost"),
            port                                = int(os.getenv("REDIS_PORT", "6379")),
            password                            = redis_password if redis_password else None,
            database_index                      = int(os.getenv("REDIS_DATABASE_INDEX", "0")),
            is_cluster                          = EnvironmentVariableHelper.get_boolean("REDIS_IS_CLUSTER", False),
            socket_timeout_second_count         = float(os.getenv("REDIS_SOCKET_TIMEOUT_SECOND_COUNT", "10.0")),
            socket_connect_timeout_second_count = float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT_SECOND_COUNT", "5.0")),
            command_maximum_retry_count         = int(os.getenv("REDIS_COMMAND_MAXIMUM_RETRY_COUNT", "1"))
        )
