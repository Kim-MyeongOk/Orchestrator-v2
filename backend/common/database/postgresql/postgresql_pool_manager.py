import asyncpg
import asyncio
import json

from typing import Optional

from common.database.postgresql.postgresql_configuration import PostgresqlConfiguration

class PostgresqlPoolManager:
    def __init__(self, postgresql_configuration : PostgresqlConfiguration) -> None:
        self.postgresql_configuration      = postgresql_configuration
        self.pool : Optional[asyncpg.Pool] = None
        self.open_lock                     = asyncio.Lock()

    @staticmethod
    async def _initialize_connection_async(connection : asyncpg.Connection) -> None:
        # JSONB 컬럼을 파이썬 dict/list로 자동 변환한다
        await connection.set_type_codec("jsonb", encoder = json.dumps, decoder = json.loads, schema = "pg_catalog")

    async def open_async(self) -> None:
        async with self.open_lock:
            if self.pool is not None:
                return
            self.pool = await asyncpg.create_pool(
                host     = self.postgresql_configuration.host,
                port     = self.postgresql_configuration.port,
                database = self.postgresql_configuration.database_name,
                user     = self.postgresql_configuration.user_name,
                password = self.postgresql_configuration.password,
                min_size = self.postgresql_configuration.minimum_connection_count,
                max_size = self.postgresql_configuration.maximum_connection_count,
                init     = PostgresqlPoolManager._initialize_connection_async
            )

    def get_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise ValueError("POSTGRESQL POOL NOT OPENED : pool")
        return self.pool

    async def close_async(self) -> None:
        async with self.open_lock:
            if self.pool is not None:
                await self.pool.close()
                self.pool = None
