from typing import Optional

from pydantic import BaseModel


class CompressedInfoResponse(BaseModel):
    # 대화 압축 결과. /stream 은 NDJSON 스트림이라 본문 JSON 이 없으므로
    # {"type" : "compressed_info", ...} 이벤트로 첫 부분에 실려 나간다.
    is_compressed : bool
    saved_tokens  : int           = 0
    summary       : Optional[str] = None
