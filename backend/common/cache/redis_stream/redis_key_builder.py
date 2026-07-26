class RedisKeyBuilder:
    @staticmethod
    def get_job_meta_key(run_id : str) -> str:
        return f"job:{{{run_id}}}:meta"

    @staticmethod
    def get_job_stream_key(run_id : str) -> str:
        return f"job:{{{run_id}}}:stream"

    @staticmethod
    def get_inflight_key(idempotency_key : str) -> str:
        return f"inflight:{{{idempotency_key}}}"

    @staticmethod
    def extract_run_id_from_key(redis_key : str) -> str:
        # "job:{<run_id>}:meta" 형태에서 run_id를 추출한다.
        return redis_key.split("{")[1].split("}")[0]
