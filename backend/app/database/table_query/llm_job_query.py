##################################################
# llm_job 테이블 쿼리 모음
#
# LLM 작업(Job) 마스터. 나머지 llm_job_* 이 이 테이블을 참조한다
#
# ⚠️ 접속 풀 : asyncpg (postgresql_pool_manager) → 플레이스홀더는 **$1, $2**
#    chat_room / chat_bookmark 는 psycopg 풀이라 %s 를 쓴다. 섞으면 런타임에 터진다.
#
# 쿼리 상수는 아직 각 리포지토리(app/llm/repository/)에 남아 있다.
# DDL 만 먼저 이 파일로 모았다 — 스키마 생성은 TableQueryRegistry 가 자동으로 수집한다.
##################################################


class LlmJobQuery:
    TABLE_NAME     = "llm_job"
    CREATION_ORDER = 110
    IS_ASYNCPG     = True

    CREATE_TABLE = """
-- 작업 마스터
CREATE TABLE IF NOT EXISTS llm_job
(
    run_id                     UUID        PRIMARY KEY,
    thread_id                  UUID        NOT NULL,
    user_id                    UUID        NOT NULL,
    job_type                   VARCHAR(20) NOT NULL,
    status                     VARCHAR(20) NOT NULL,
    output_format              VARCHAR(20) NOT NULL DEFAULT 'deepagents',
    request_payload            JSONB       NOT NULL,
    error_message              TEXT,
    usage                      JSONB,
    message_count              INTEGER     NOT NULL DEFAULT 0,
    event_count                INTEGER     NOT NULL DEFAULT 0,
    last_sequence_number       INTEGER     NOT NULL DEFAULT 0,
    chunk_count                INTEGER     NOT NULL DEFAULT 0,
    task_count                 INTEGER     NOT NULL DEFAULT 0,
    turn_number                INTEGER     NOT NULL DEFAULT 1,
    has_complete_chunk_history BOOLEAN     NOT NULL DEFAULT TRUE,
    runtime_metadata           JSONB,
    idempotency_key            VARCHAR(200),
    created_user_id            UUID        NOT NULL,
    updated_user_id            UUID        NOT NULL,
    created_at                 TIMESTAMPTZ NOT NULL,
    started_at                 TIMESTAMPTZ,
    completed_at               TIMESTAMPTZ,
    updated_at                 TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_llm_job_user_created        ON llm_job (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_llm_job_user_status         ON llm_job (user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_llm_job_thread              ON llm_job (thread_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_llm_job_active_updated      ON llm_job (updated_at) WHERE status IN ('pending', 'running');

CREATE UNIQUE INDEX IF NOT EXISTS uq_llm_job_idempotency   ON llm_job (idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_llm_job_thread_active ON llm_job (thread_id) WHERE status IN ('pending', 'running');

ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS last_sequence_number INTEGER NOT NULL DEFAULT 0;

ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS chunk_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS task_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS turn_number INTEGER NOT NULL DEFAULT 1;

ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS has_complete_chunk_history BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS runtime_metadata JSONB;

-- 오케스트레이터 도메인 통합 컬럼 (orch_run / orch_message 흡수)
ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS final_output JSONB;

ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS aggregated_event JSONB;
"""
