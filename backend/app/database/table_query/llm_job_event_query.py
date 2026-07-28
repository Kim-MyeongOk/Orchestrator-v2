##################################################
# llm_job_event 테이블 쿼리 모음
#
# Job 수명주기 이벤트 로그
#
# ⚠️ 접속 풀 : asyncpg (postgresql_pool_manager) → 플레이스홀더는 **$1, $2**
#    chat_room / chat_bookmark 는 psycopg 풀이라 %s 를 쓴다. 섞으면 런타임에 터진다.
#
# 쿼리 상수는 아직 각 리포지토리(app/llm/repository/)에 남아 있다.
# DDL 만 먼저 이 파일로 모았다 — 스키마 생성은 TableQueryRegistry 가 자동으로 수집한다.
##################################################


class LlmJobEventQuery:
    TABLE_NAME     = "llm_job_event"
    CREATION_ORDER = 170
    IS_ASYNCPG     = True

    CREATE_TABLE = """
-- tasks / custom 이벤트 로그 (청크 단위 저장)
CREATE TABLE IF NOT EXISTS llm_job_event (
    id         UUID        PRIMARY KEY,
    run_id     UUID        NOT NULL,
    seq        INTEGER     NOT NULL,
    chunk_type VARCHAR(20) NOT NULL,
    ns_path    TEXT        NOT NULL DEFAULT '',
    data       JSONB       NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (run_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_llm_job_event_run ON llm_job_event (run_id, seq);
"""
