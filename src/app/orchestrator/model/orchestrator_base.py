##################################################
# 오케스트레이터 ORM 베이스
# orch_* 테이블 전체가 공유하는 SQLAlchemy DeclarativeBase.
##################################################

# uv add sqlalchemy[asyncio]
from sqlalchemy.orm import DeclarativeBase


class OrchestratorBase(DeclarativeBase):
    pass
