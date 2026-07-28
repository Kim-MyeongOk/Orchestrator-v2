##################################################
# chat_user 테이블 쿼리 모음
#
# 로그인 계정. user_id 는 로그인 식별자이자 채팅 스코핑 키로,
# chat_room.user_id(TEXT) 와 같은 타입이라 방 목록/대화가 같은 ID 로 이어진다.
#
# ⚠️ 접속 풀 : asyncpg (postgresql_pool_manager) → 플레이스홀더가 %s 가 아니라 **$1, $2** 다.
#    chat_room / chat_bookmark 는 psycopg 풀을 써서 %s 를 쓴다. 두 스타일을 섞으면 런타임에 터진다.
##################################################


class ChatUserQuery:
    TABLE_NAME     = "chat_user"
    CREATION_ORDER = 5    # 다른 테이블을 참조하지 않으므로 먼저 만들어도 된다
    IS_ASYNCPG     = True # 스키마 초기화기가 어느 풀로 실행할지 판단한다

    ##################################################
    # DDL
    ##################################################

    CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS chat_user
(
    user_id       TEXT        PRIMARY KEY,
    password_hash TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

    ##################################################
    # 조회
    ##################################################

    SELECT_PASSWORD_HASH = "SELECT password_hash FROM chat_user WHERE user_id = $1"

    ##################################################
    # 변경
    ##################################################

    # 조회 후 삽입이 아니라 한 문장으로 처리한다 — 같은 ID 로 동시에 가입 요청이 들어와도 한쪽만 성공한다.
    # 중복이면 RETURNING 이 비어 있어 호출부가 409 로 응답한다.
    INSERT_IF_ABSENT = (
        "INSERT INTO chat_user (user_id, password_hash, created_at) VALUES ($1, $2, $3) "
        "ON CONFLICT (user_id) DO NOTHING RETURNING TRUE")
