##################################################
# 대화 스레드 테이블 (orch_thread)
# 사용자 대화의 최상위 묶음 단위. thread_id 는 20만 사용자 규모에서
# 해시 기반 파티셔닝의 파티션 키로 사용된다.
##################################################

from datetime import datetime
from datetime import timezone

from sqlalchemy     import DateTime
from sqlalchemy     import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.orchestrator.model.orchestrator_base import OrchestratorBase


class OrchThread(OrchestratorBase):
    __tablename__ = "orch_thread"

    thread_id  : Mapped[str]      = mapped_column(String(64), primary_key = True)                                            # 스레드 ID (파티션 해시 키)
    created_at : Mapped[datetime] = mapped_column(DateTime(timezone = True), default = lambda : datetime.now(timezone.utc))  # 생성 시각
    updated_at : Mapped[datetime] = mapped_column(DateTime(timezone = True), default = lambda : datetime.now(timezone.utc))  # 마지막 대화 시각
