##################################################
# llm_job_task 테이블 쿼리 모음
#
# Job 내부 태스크(서브에이전트/도구 호출) 진행 상태
#
# ⚠️ 접속 풀 : asyncpg (postgresql_pool_manager) → 플레이스홀더는 **$1, $2**
#    chat_room / chat_bookmark 는 psycopg 풀이라 %s 를 쓴다. 섞으면 런타임에 터진다.
#
# 쿼리 상수는 아직 각 리포지토리(app/llm/repository/)에 남아 있다.
# DDL 만 먼저 이 파일로 모았다 — 스키마 생성은 TableQueryRegistry 가 자동으로 수집한다.
##################################################


class LlmJobTaskQuery:
    TABLE_NAME     = "llm_job_task"
    CREATION_ORDER = 160
    IS_ASYNCPG     = True

    CREATE_TABLE = """
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
"""
