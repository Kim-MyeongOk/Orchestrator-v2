##################################################
# 실행 단위 테이블 (orch_run)
# 그래프 실행 1회의 최초 입력값(initial_input)과 최종 출력값(final_output)을 저장한다.
# tasks / custom 청크의 병합본은 aggregated_event 에 함께 보관하여
# run 단위 전체 맥락(Context) 관리에 활용한다.
##################################################

from typing   import Any
from typing   import Dict
from typing   import Optional
from datetime import datetime
from datetime import timezone

from sqlalchemy                     import DateTime
from sqlalchemy                     import ForeignKey
from sqlalchemy                     import Index
from sqlalchemy                     import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm                 import Mapped
from sqlalchemy.orm                 import mapped_column

from app.orchestrator.model.orchestrator_base import OrchestratorBase


class OrchRun(OrchestratorBase):
    __tablename__  = "orch_run"
    __table_args__ = (
        # 스레드별 실행 이력 조회용 복합 인덱스 (키셋 페이징 대응)
        Index("ix_orch_run_thread_created", "thread_id", "created_at"),
    )

    run_id           : Mapped[str]                      = mapped_column(String(64), primary_key = True)                                            # 실행 ID
    thread_id        : Mapped[str]                      = mapped_column(String(64), ForeignKey("orch_thread.thread_id"))                           # 소속 스레드 ID
    initial_input    : Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable = True)                                                    # 이번 run 의 최초 입력값
    final_output     : Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable = True)                                                    # values 청크 중 가장 마지막(최신) 상태
    aggregated_event : Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable = True)                                                    # tasks / custom 청크 병합본
    created_at       : Mapped[datetime]                 = mapped_column(DateTime(timezone = True), default = lambda : datetime.now(timezone.utc))  # 생성 시각
