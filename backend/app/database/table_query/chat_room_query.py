##################################################
# chat_room 테이블 쿼리 모음
#
# 유저별 채팅방 목록. 대화 내용은 체크포인트가 원본이므로 여기는 목록/메타와 요약 상태만 저장한다.
#
# 접속 풀 : psycopg (checkpoint_connection_pool) → 플레이스홀더는 %s
##################################################


class ChatRoomQuery:
    TABLE_NAME     = "chat_room"
    CREATION_ORDER = 10   # chat_bookmark 가 이 테이블을 참조하므로 먼저 만들어져야 한다

    ##################################################
    # DDL
    ##################################################

    # 요약 칼럼(summary / summarized_message_count / summary_updated_at)은
    # 기존 배포에도 붙어야 하므로 CREATE 가 아니라 ADD COLUMN IF NOT EXISTS 로 추가한다.
    # summarized_message_count : 어디까지 요약에 반영했는지 — 없으면 압축할 때마다 옛 대화를 다시 요약한다.
    CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS chat_room
(
    room_id          TEXT        PRIMARY KEY,
    user_id          TEXT        NOT NULL,
    thread_id        TEXT        NOT NULL,
    title            TEXT        NOT NULL DEFAULT '새 대화',
    model            TEXT,
    reasoning_effort TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_room_user_updated ON chat_room (user_id, updated_at DESC);

ALTER TABLE chat_room ADD COLUMN IF NOT EXISTS summary                  TEXT;
ALTER TABLE chat_room ADD COLUMN IF NOT EXISTS summarized_message_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE chat_room ADD COLUMN IF NOT EXISTS summary_updated_at       TIMESTAMPTZ;
"""

    ##################################################
    # 조회
    ##################################################

    SELECT_LIST_BY_USER = (
        "SELECT room_id, thread_id, title, model, reasoning_effort FROM chat_room "
        "WHERE user_id = %s ORDER BY updated_at DESC")

    # 스레드 소유권 검증 : 다른 사용자가 소유한 thread_id 인지만 본다 (있으면 403)
    SELECT_FOREIGN_OWNER_BY_THREAD = (
        "SELECT 1 FROM chat_room WHERE thread_id = %s AND user_id <> %s LIMIT 1")

    # 방 소유권 검증 : 본인 소유가 아니거나 없는 방이면 결과가 비어 있다
    SELECT_OWNED_ROOM = "SELECT 1 FROM chat_room WHERE room_id = %s AND user_id = %s"

    SELECT_SUMMARY = "SELECT summary, summarized_message_count FROM chat_room WHERE thread_id = %s LIMIT 1"

    ##################################################
    # 변경
    ##################################################

    # 소유자가 다르면 WHERE 절에서 걸러져 rowcount 가 0 이 된다 (남의 방 갈취 방지)
    UPSERT = (
        "INSERT INTO chat_room (room_id, user_id, thread_id, title, model, reasoning_effort) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (room_id) DO UPDATE SET thread_id = EXCLUDED.thread_id, title = EXCLUDED.title, "
        "model = EXCLUDED.model, reasoning_effort = EXCLUDED.reasoning_effort, updated_at = NOW() "
        "WHERE chat_room.user_id = EXCLUDED.user_id")

    DELETE_BY_OWNER = "DELETE FROM chat_room WHERE room_id = %s AND user_id = %s"

    UPDATE_SUMMARY = (
        "UPDATE chat_room SET summary = %s, summarized_message_count = %s, summary_updated_at = NOW() "
        "WHERE thread_id = %s")

    CLEAR_SUMMARY = (
        "UPDATE chat_room SET summary = NULL, summarized_message_count = 0, summary_updated_at = NULL "
        "WHERE thread_id = %s")
