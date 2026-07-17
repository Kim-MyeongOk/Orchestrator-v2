from dataclasses import dataclass

@dataclass(frozen = True, slots = True)
class JobConfiguration:
    execution_timeout_second_count    : int = 3600  # 작업 실행 시간 상한(초) (기본값 : 3600)
    redis_safety_ttl_second_count     : int = 3900  # 실행 중 Redis 안전 TTL(초) (기본값 : 3900)
    redis_grace_ttl_second_count      : int = 300   # 종료 후 Redis 유예 TTL(초) (기본값 : 300)
    redis_stream_maximum_length       : int = 10000 # Redis stream 근사 최대 길이 (기본값 : 10000)
    heartbeat_interval_second_count   : int = 10    # heartbeat 갱신 주기(초) (기본값 : 10)
    heartbeat_expire_second_count     : int = 30    # 고아 작업 판정 시간(초) (기본값 : 30)
    xread_block_millisecond_count     : int = 5000  # XREAD BLOCK 대기 시간(ms) (기본값 : 5000)
    idempotency_lock_ttl_second_count : int = 3600  # 멱등성 락 TTL(초) (기본값 : 3600)
