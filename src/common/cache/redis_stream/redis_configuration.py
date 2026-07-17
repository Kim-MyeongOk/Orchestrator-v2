from dataclasses import dataclass
from typing      import Optional

@dataclass(frozen = True, slots = True)
class RedisConfiguration:
    host                                : str           = "localhost" # 호스트 (기본값 : localhost)
    port                                : int           = 6379        # 포트 (기본값 : 6379)
    password                            : Optional[str] = None        # 비밀번호 (기본값 : None)
    database_index                      : int           = 0           # 데이터베이스 인덱스 (Cluster에서는 무시, 기본값 : 0)
    is_cluster                          : bool          = False       # Redis Cluster 사용 여부 (기본값 : False)
    socket_timeout_second_count         : float         = 10.0        # 소켓 응답 타임아웃(초) (기본값 : 10.0)
    socket_connect_timeout_second_count : float = 5.0                 # 소켓 연결 타임아웃(초) (기본값 : 5.0)
    command_maximum_retry_count         : int           = 1           # 명령 재시도 횟수 (기본값 : 1)
