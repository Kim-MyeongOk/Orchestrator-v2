##################################################
# llm_thread_message 테이블 쿼리 모음
#
# 스레드에 확정 저장된 메시지 (턴/순서 단위)
#
# ⚠️ 접속 풀 : asyncpg (postgresql_pool_manager) → 플레이스홀더는 **$1, $2**
#    chat_room / chat_bookmark 는 psycopg 풀이라 %s 를 쓴다. 섞으면 런타임에 터진다.
#
# 쿼리 상수는 아직 각 리포지토리(app/llm/repository/)에 남아 있다.
# DDL 만 먼저 이 파일로 모았다 — 스키마 생성은 TableQueryRegistry 가 자동으로 수집한다.
##################################################


class LlmThreadMessageQuery:
    TABLE_NAME     = "llm_thread_message"
    CREATION_ORDER = 140
    IS_ASYNCPG     = True

    CREATE_TABLE = """
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
"""
