from typing   import Optional
from datetime import datetime
from datetime import timezone

from app.database.table_query.chat_user_query           import ChatUserQuery
from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager

class UserRepository:
    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager) -> None:
        self.postgresql_pool_manager = postgresql_pool_manager

    async def create_user_async(self, user_id : str, password_hash : str) -> bool:
        # 신규 사용자 등록 : 이미 존재하는 user_id 면 삽입하지 않고 False 반환 (중복 등록 방지)
        current_time = datetime.now(timezone.utc)
        query_text   = ChatUserQuery.INSERT_IF_ABSENT
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            is_inserted = await connection.fetchval(query_text, user_id, password_hash, current_time)
            return bool(is_inserted)

    async def get_password_hash_async(self, user_id : str) -> Optional[str]:
        # 로그인 검증용 : user_id 의 저장된 비밀번호 해시를 반환한다 (없으면 None)
        query_text = ChatUserQuery.SELECT_PASSWORD_HASH
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            return await connection.fetchval(query_text, user_id)
