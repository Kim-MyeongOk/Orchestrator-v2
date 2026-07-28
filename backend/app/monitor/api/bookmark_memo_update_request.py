from typing import Optional

from pydantic import BaseModel


class BookmarkMemoUpdateRequest(BaseModel):
    # 메모만 부분 수정한다 (PATCH). 빈 문자열이면 메모 삭제로 취급해 NULL 로 저장한다.
    memo : Optional[str] = None
