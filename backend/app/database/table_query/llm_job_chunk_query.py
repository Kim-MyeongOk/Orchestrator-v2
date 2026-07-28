##################################################
# llm_job_chunk 테이블 쿼리 모음
#
# 스트리밍 청크 아카이브 (Redis 버퍼 → 벌크 flush 대상)
#
# ⚠️ 접속 풀 : asyncpg (postgresql_pool_manager) → 플레이스홀더는 **$1, $2**
#    chat_room / chat_bookmark 는 psycopg 풀이라 %s 를 쓴다. 섞으면 런타임에 터진다.
#
# 쿼리 상수는 아직 각 리포지토리(app/llm/repository/)에 남아 있다.
# DDL 만 먼저 이 파일로 모았다 — 스키마 생성은 TableQueryRegistry 가 자동으로 수집한다.
##################################################


class LlmJobChunkQuery:
    TABLE_NAME     = "llm_job_chunk"
    CREATION_ORDER = 150
    IS_ASYNCPG     = True

    CREATE_TABLE = """
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
"""
