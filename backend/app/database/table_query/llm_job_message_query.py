##################################################
# llm_job_message 테이블 쿼리 모음
#
# Job 이 만든 메시지 (run 단위)
#
# ⚠️ 접속 풀 : asyncpg (postgresql_pool_manager) → 플레이스홀더는 **$1, $2**
#    chat_room / chat_bookmark 는 psycopg 풀이라 %s 를 쓴다. 섞으면 런타임에 터진다.
#
# 쿼리 상수는 아직 각 리포지토리(app/llm/repository/)에 남아 있다.
# DDL 만 먼저 이 파일로 모았다 — 스키마 생성은 TableQueryRegistry 가 자동으로 수집한다.
##################################################


class LlmJobMessageQuery:
    TABLE_NAME     = "llm_job_message"
    CREATION_ORDER = 130
    IS_ASYNCPG     = True

    CREATE_TABLE = """
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

ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS task_id VARCHAR(200);

ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS parent_task_id VARCHAR(200);

ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS message_metadata JSONB;

ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS message_type VARCHAR(50);

ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS tool_call_id VARCHAR(200);

ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS agent_name VARCHAR(200);

ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS is_root_message BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_llm_job_message_task   ON llm_job_message (run_id, task_id, seq_first);

ALTER TABLE llm_job_message ADD COLUMN IF NOT EXISTS files_metadata JSONB;
"""
