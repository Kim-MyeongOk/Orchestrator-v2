from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class StreamRequest(BaseModel):
    thread_id         : str
    message           : str
    model             : Optional[str] = None    # 요청별 모델 선택 (미지정 시 .env 기본 모델)
    reasoning_effort  : Optional[str] = None    # 생각 강도 : low | medium | high | None(모델 기본)
    include_reasoning : bool          = False   # True : NDJSON 이벤트 스트림({"type":"reasoning"|"token","text":...}) 으로 생각 과정을 함께 전송
                                                # False : 답변 토큰만 평문 스트림 (기존 클라이언트 하위호환)
    referenced_text   : Optional[str] = None    # 이전 답변에서 드래그해 "참조하기"로 담은 발췌.
                                                # 있으면 [참조 내용]/[질문] 두 블록으로 조합해 모델에 전달한다.
    preset_name       : Optional[str] = None    # LLM 파라미터 프리셋: LOW / MEDIUM / HIGH
                                                # 지정 시 온도, top_p, max_tokens 등 하이퍼파라미터를 적용한다.
    referenced_message_id_list : List[str] = Field(default_factory = list)
                                                # 우클릭으로 통째로 고른 이전 답변들의 ID ("agent-0", "agent-3" …).
                                                # 체크포인트에서 본문을 찾아 <referenced_context> 블록으로 묶어 전달한다.
    image_url_list : List[str] = Field(default_factory = list)
                                                # POST /api/upload 로 MinIO 에 올린 이미지들의 접근 URL.
                                                # 있으면 질문을 OpenAI 멀티모달 규격(text + image_url 블록)으로 조립해 Vision 모델에 넘긴다.
