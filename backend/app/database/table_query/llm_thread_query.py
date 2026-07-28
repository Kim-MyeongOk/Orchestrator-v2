##################################################
# llm_thread 테이블 쿼리 모음
#
# 대화 스레드 목록 (Job 서비스용)
#
# ⚠️ 접속 풀 : asyncpg (postgresql_pool_manager) → 플레이스홀더는 **$1, $2**
#    chat_room / chat_bookmark 는 psycopg 풀이라 %s 를 쓴다. 섞으면 런타임에 터진다.
#
# 쿼리 상수는 아직 각 리포지토리(app/llm/repository/)에 남아 있다.
# DDL 만 먼저 이 파일로 모았다 — 스키마 생성은 TableQueryRegistry 가 자동으로 수집한다.
##################################################


class LlmThreadQuery:
    TABLE_NAME     = "llm_thread"
    CREATION_ORDER = 120
    IS_ASYNCPG     = True

    CREATE_TABLE = """
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
"""
