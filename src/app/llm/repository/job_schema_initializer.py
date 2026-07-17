from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager

class JobSchemaInitializer:
    SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS llm_schema_migration
(
    version    INTEGER      PRIMARY KEY,
    name       VARCHAR(200) NOT NULL,
    applied_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

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

CREATE TABLE IF NOT EXISTS llm_thread
(
    thread_id            UUID        PRIMARY KEY,
    user_id              UUID        NOT NULL,
    title                TEXT        NOT NULL,
    last_message_preview TEXT,
    latest_run_id        UUID,
    latest_status        VARCHAR(20),
    created_at           TIMESTAMPTZ NOT NULL,
    updated_at           TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_llm_thread_user_updated ON llm_thread (user_id, updated_at DESC, thread_id DESC);

-- 병합 메시지 (messages 청크의 최종 병합 결과)
CREATE TABLE IF NOT EXISTS llm_job_message
(
    id                UUID         PRIMARY KEY,
    run_id            UUID         NOT NULL,
    thread_id         UUID         NOT NULL,
    message_id        VARCHAR(200) NOT NULL,
    ns_path           TEXT         NOT NULL DEFAULT '',
    task_id           VARCHAR(200),
    parent_task_id    VARCHAR(200),
    message_metadata  JSONB,
    message_type      VARCHAR(50),
    tool_call_id      VARCHAR(200),
    agent_name        VARCHAR(200),
    is_root_message   BOOLEAN      NOT NULL DEFAULT FALSE,
    role              VARCHAR(20)  NOT NULL,
    content           JSONB        NOT NULL,
    tool_call_list    JSONB,
    usage             JSONB,
    response_metadata JSONB,
    seq_first         INTEGER      NOT NULL,
    seq_last          INTEGER      NOT NULL,
    created_at        TIMESTAMPTZ  NOT NULL,
    UNIQUE (run_id, ns_path, message_id)
);

CREATE INDEX IF NOT EXISTS idx_llm_job_message_run    ON llm_job_message (run_id, seq_first);
CREATE INDEX IF NOT EXISTS idx_llm_job_message_thread ON llm_job_message (thread_id, created_at);

CREATE TABLE IF NOT EXISTS llm_thread_message
(
    id                 UUID         PRIMARY KEY,
    thread_id          UUID         NOT NULL,
    run_id             UUID         NOT NULL,
    turn_number        INTEGER      NOT NULL,
    message_order      INTEGER      NOT NULL,
    role               VARCHAR(20)  NOT NULL,
    content            TEXT         NOT NULL,
    source_message_id  VARCHAR(200),
    source_task_id     VARCHAR(200),
    is_display_message BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ  NOT NULL,
    UNIQUE (run_id, message_order, role)
);

CREATE INDEX IF NOT EXISTS idx_llm_thread_message_thread ON llm_thread_message (thread_id, turn_number, message_order);

CREATE TABLE IF NOT EXISTS llm_job_chunk
(
    id                UUID         PRIMARY KEY,
    run_id            UUID         NOT NULL,
    seq               INTEGER      NOT NULL,
    chunk_type        VARCHAR(20)  NOT NULL,
    ns_list           JSONB        NOT NULL,
    ns_path           TEXT         NOT NULL DEFAULT '',
    task_id           VARCHAR(200),
    parent_task_id    VARCHAR(200),
    task_link_type    VARCHAR(20),
    data              JSONB        NOT NULL,
    stream_version    VARCHAR(50)  NOT NULL DEFAULT 'langgraph-v2',
    schema_version    INTEGER      NOT NULL DEFAULT 1,
    projection_status VARCHAR(20)  NOT NULL DEFAULT 'pending',
    created_at        TIMESTAMPTZ  NOT NULL,
    UNIQUE (run_id, seq),
    CHECK (seq > 0),
    CHECK (chunk_type IN ('tasks', 'messages', 'custom'))
);

CREATE INDEX IF NOT EXISTS idx_llm_job_chunk_run_task ON llm_job_chunk (run_id, task_id, seq);
CREATE INDEX IF NOT EXISTS idx_llm_job_chunk_run_type ON llm_job_chunk (run_id, chunk_type, seq);

CREATE TABLE IF NOT EXISTS llm_job_task
(
    run_id                    UUID         NOT NULL,
    task_id                   VARCHAR(200) NOT NULL,
    parent_task_id            VARCHAR(200),
    task_name                 VARCHAR(200),
    agent_name                VARCHAR(200),
    status                    VARCHAR(30)  NOT NULL,
    input                     JSONB,
    result                    JSONB,
    error_message             TEXT,
    interrupt_list            JSONB,
    trigger_list              JSONB,
    metadata                  JSONB,
    started_sequence_number   INTEGER,
    completed_sequence_number INTEGER,
    started_at                TIMESTAMPTZ,
    completed_at              TIMESTAMPTZ,
    updated_at                TIMESTAMPTZ NOT NULL,
    is_status_inferred        BOOLEAN     NOT NULL DEFAULT FALSE,
    PRIMARY KEY (run_id, task_id)
);

CREATE INDEX IF NOT EXISTS idx_llm_job_task_run_status ON llm_job_task (run_id, status, started_sequence_number);

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

ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS last_sequence_number INTEGER NOT NULL DEFAULT 0;
ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS chunk_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS task_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS turn_number INTEGER NOT NULL DEFAULT 1;
ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS has_complete_chunk_history BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS runtime_metadata JSONB;
ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS task_id VARCHAR(200);
ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS parent_task_id VARCHAR(200);
ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS message_metadata JSONB;
ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS message_type VARCHAR(50);
ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS tool_call_id VARCHAR(200);
ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS agent_name VARCHAR(200);
ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS is_root_message BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_llm_job_message_task   ON llm_job_message (run_id, task_id, seq_first);

-- 오케스트레이터 도메인 통합 컬럼 (orch_run / orch_message 흡수)
ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS final_output JSONB;
ALTER TABLE llm_job         ADD COLUMN IF NOT EXISTS aggregated_event JSONB;
ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS files_metadata JSONB;
"""

    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager) -> None:
        self.postgresql_pool_manager = postgresql_pool_manager

    async def initialize_schema_async(self) -> None:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            await connection.execute(JobSchemaInitializer.SCHEMA_DDL)
