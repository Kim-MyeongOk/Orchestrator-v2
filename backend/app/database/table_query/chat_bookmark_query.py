##################################################
# chat_bookmark 테이블 쿼리 모음
#
# 북마크는 "방 안에서 N 번째 답변"(agent_index) 단위로 저장한다.
# chat_room 에 불리언 칼럼을 두지 않는 이유 : thread_id 는 대화 전체를 가리키므로 답변 하나를 지목할 수 없다.
# text 는 미리보기 스냅샷 — 이게 없으면 사이드바 목록을 그릴 때마다 방마다 체크포인트를 통째로 열어야 한다.
#
# 접속 풀 : psycopg (checkpoint_connection_pool) → 플레이스홀더는 %s
##################################################


class ChatBookmarkQuery:
    TABLE_NAME     = "chat_bookmark"
    CREATION_ORDER = 20   # chat_room 을 REFERENCES 하므로 그 뒤에 만들어져야 한다

    ##################################################
    # DDL
    ##################################################

    # memo 는 기존 배포에도 붙어야 하므로 CREATE 가 아니라 ADD COLUMN IF NOT EXISTS 로 추가한다.
    # NULL 은 "메모 없음" — 빈 문자열과 구분해 두어야 upsert 시 COALESCE 로 기존 메모를 보존할 수 있다.
    CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS chat_bookmark
(
    bookmark_id  TEXT        PRIMARY KEY,
    user_id      TEXT        NOT NULL,
    room_id      TEXT        NOT NULL REFERENCES chat_room (room_id) ON DELETE CASCADE,
    agent_index  INTEGER     NOT NULL,
    text         TEXT        NOT NULL DEFAULT '',
    completed_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (room_id, agent_index)
);
CREATE INDEX IF NOT EXISTS idx_chat_bookmark_user_created ON chat_bookmark (user_id, created_at DESC);

ALTER TABLE chat_bookmark ADD COLUMN IF NOT EXISTS memo TEXT;
"""

    ##################################################
    # 조회
    ##################################################

    SELECT_LIST_BY_USER = (
        "SELECT bookmark_id, room_id, agent_index, text, memo, "
        "       (EXTRACT(EPOCH FROM completed_at) * 1000)::BIGINT AS completed_at, "
        "       (EXTRACT(EPOCH FROM created_at)   * 1000)::BIGINT AS created_at "
        "FROM chat_bookmark WHERE user_id = %s ORDER BY created_at DESC")

    ##################################################
    # 변경
    ##################################################

    # 같은 답변을 다시 북마크하면 미리보기 스냅샷만 갱신한다 (중복 행을 만들지 않는다).
    # 메모는 COALESCE 로 보존한다 — 캐시 재등록처럼 메모를 싣지 않은 요청이 기존 메모를 지우면 안 된다.
    UPSERT = (
        "INSERT INTO chat_bookmark (bookmark_id, user_id, room_id, agent_index, text, completed_at, memo) "
        "VALUES (%s, %s, %s, %s, %s, TO_TIMESTAMP(%s), %s) "
        "ON CONFLICT (room_id, agent_index) DO UPDATE SET bookmark_id = EXCLUDED.bookmark_id, "
        "text = EXCLUDED.text, completed_at = EXCLUDED.completed_at, "
        "memo = COALESCE(EXCLUDED.memo, chat_bookmark.memo)")

    UPDATE_MEMO_BY_OWNER = "UPDATE chat_bookmark SET memo = %s WHERE bookmark_id = %s AND user_id = %s"

    DELETE_BY_OWNER = "DELETE FROM chat_bookmark WHERE bookmark_id = %s AND user_id = %s"

    # 질문 수정으로 대화가 절단된 경우 : 잘려나간 답변을 가리키던 북마크를 함께 정리한다.
    # agent_index 는 위치 기반이라 남겨두면 엉뚱한 답변을 가리키게 된다.
    DELETE_FROM_AGENT_INDEX = (
        "DELETE FROM chat_bookmark WHERE agent_index >= %s AND room_id IN "
        "(SELECT room_id FROM chat_room WHERE thread_id = %s AND user_id = %s)")
