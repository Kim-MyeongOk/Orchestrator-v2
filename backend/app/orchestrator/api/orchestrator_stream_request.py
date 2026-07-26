##################################################
# 오케스트레이터 스트리밍 요청 모델
# POST /api/v1/orchestrator/stream 의 요청 본문.
##################################################

import uuid

# uv add pydantic
from typing   import Any
from typing   import Dict
from typing   import List
from typing   import Optional
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class OrchestratorStreamRequest(BaseModel):
    model_config = ConfigDict(extra = "forbid")

    thread_id      : Optional[uuid.UUID]            = None                  # 대화 스레드 ID (없으면 서버가 UUID v7 로 신규 발급)
    user_message   : str                            = Field(min_length = 1)  # 이번 턴의 사용자 질문
    files_metadata : Optional[List[Dict[str, Any]]] = None                  # [{"file_url", "file_type", "file_name"}, ...] (멀티모달 확장)
