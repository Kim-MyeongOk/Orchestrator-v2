##################################################
# SQLAlchemy 비동기 엔진 관리자
# PostgreSQL 비동기 엔진과 세션 팩토리의 생성/해제를 담당한다.
##################################################

# uv add sqlalchemy[asyncio]
# uv add asyncpg
from typing                 import Optional
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine


class SqlalchemyEngineManager:
    def __init__(self, database_url : str, minimum_connection_count : int = 1, maximum_connection_count : int = 10, is_echo : bool = False):
        self.database_url             = database_url              # 예 : postgresql+asyncpg://user:password@localhost:5432/postgres
        self.minimum_connection_count = minimum_connection_count  # 풀 기본 커넥션 수 (기본값 : 1)
        self.maximum_connection_count = maximum_connection_count  # 풀 최대 커넥션 수 (기본값 : 10)
        self.is_echo                  = is_echo                   # SQL 로그 출력 여부 (기본값 : False)
        self.async_engine             : Optional[AsyncEngine]        = None
        self.async_session_factory    : Optional[async_sessionmaker] = None

    def open(self) -> None:
        self.async_engine          = create_async_engine(self.database_url, echo = self.is_echo, pool_size = self.minimum_connection_count, max_overflow = self.maximum_connection_count - self.minimum_connection_count, pool_pre_ping = True)
        self.async_session_factory = async_sessionmaker(bind = self.async_engine, class_ = AsyncSession, expire_on_commit = False)

    async def close_async(self) -> None:
        if self.async_engine is not None:
            await self.async_engine.dispose()
            self.async_engine          = None
            self.async_session_factory = None
