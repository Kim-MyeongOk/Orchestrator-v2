from typing   import Optional
from datetime import datetime
from datetime import timezone

from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager

class UserRepository:
    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager) -> None:
        self.postgresql_pool_manager = postgresql_pool_manager

    async def create_user_async(self, user_id : str, password_hash : str) -> bool:
        # 신규 사용자 등록 : 이미 존재하는 user_id 면 삽입하지 않고 False 반환 (중복 등록 방지)
        current_time = datetime.now(timezone.utc)
        query_text   = "INSERT INTO chat_user (user_id, password_hash, created_at) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO NOTHING RETURNING TRUE"
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            is_inserted = await connection.fetchval(query_text, user_id, password_hash, current_time)
            return bool(is_inserted)

    async def get_password_hash_async(self, user_id : str) -> Optional[str]:
        # 로그인 검증용 : user_id 의 저장된 비밀번호 해시를 반환한다 (없으면 None)
        query_text = "SELECT password_hash FROM chat_user WHERE user_id = $1"
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            return await connection.fetchval(query_text, user_id)
