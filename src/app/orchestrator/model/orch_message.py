##################################################
# 메시지 테이블 (orch_message)
# 청크 병합이 끝난 완성 메시지를 1행으로 저장한다.
# files_metadata 에 이미지/문서 정보(URL, 파일 타입 등)를 구조화하여
# 대화 이력 복원 시 멀티모달 메시지 형태로 되살릴 수 있게 한다.
##################################################

from typing   import Any
from typing   import Dict
from typing   import List
from typing   import Optional
from datetime import datetime
from datetime import timezone

from sqlalchemy                     import DateTime
from sqlalchemy                     import ForeignKey
from sqlalchemy                     import Index
from sqlalchemy                     import Integer
from sqlalchemy                     import String
from sqlalchemy                     import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm                 import Mapped
from sqlalchemy.orm                 import mapped_column

from app.orchestrator.model.orchestrator_base import OrchestratorBase


class OrchMessage(OrchestratorBase):
    __tablename__  = "orch_message"
    __table_args__ = (
        # 이력 복원 쿼리(WHERE thread_id ORDER BY created_at, message_order)용 복합 인덱스
        Index("ix_orch_message_thread_created", "thread_id", "created_at", "message_order"),
    )

    message_id     : Mapped[str]                            = mapped_column(String(128), primary_key = True)                                          # 메시지 ID (LangChain id, 없으면 합성 ID)
    thread_id      : Mapped[str]                            = mapped_column(String(64), ForeignKey("orch_thread.thread_id"))                          # 소속 스레드 ID
    run_id         : Mapped[str]                            = mapped_column(String(64))                                                              # 소속 실행 ID (요구 스키마 확장 : run 단위 추적용)
    message_order  : Mapped[int]                            = mapped_column(Integer, default = 0)                                                    # run 내 메시지 순서 (created_at 동률 대비)
    role           : Mapped[str]                            = mapped_column(String(20))                                                              # human / ai / tool / system
    content        : Mapped[str]                            = mapped_column(Text)                                                                    # 병합 완료된 메시지 본문
    files_metadata : Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONB, nullable = True)                                                  # [{"file_url", "file_type", "file_name"}, ...]
    created_at     : Mapped[datetime]                       = mapped_column(DateTime(timezone = True), default = lambda : datetime.now(timezone.utc))  # 생성 시각
