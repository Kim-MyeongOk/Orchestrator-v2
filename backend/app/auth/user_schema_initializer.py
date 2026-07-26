from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager

##################################################
# 사용자 스키마 초기화기
# 로그인 계정 테이블(chat_user)을 생성한다. user_id 는 로그인 식별자이자 채팅 스코핑 키로,
# chat_room.user_id(TEXT)와 동일한 타입이라 방 목록/대화가 같은 ID 로 이어진다.
##################################################
class UserSchemaInitializer:
    SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS chat_user
(
    user_id       TEXT        PRIMARY KEY,
    password_hash TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager) -> None:
        self.postgresql_pool_manager = postgresql_pool_manager

    async def initialize_schema_async(self) -> None:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            await connection.execute(UserSchemaInitializer.SCHEMA_DDL)
