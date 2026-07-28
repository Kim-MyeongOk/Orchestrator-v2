from typing import Optional

from pydantic import BaseModel


class BookmarkUpsertRequest(BaseModel):
    # 북마크 대상은 "방 안에서 몇 번째 답변인가"(agent_index) 로 식별한다.
    # thread_id 는 대화 전체를 가리키는 값이라 답변 하나를 지목할 수 없어 쓰지 않는다.
    bookmark_id  : str
    room_id      : str
    agent_index  : int
    text         : str            = ""     # 목록 미리보기용 스냅샷 (체크포인트를 열지 않고 사이드바를 그리기 위함)
    completed_at : Optional[int]  = None   # 답변 완료 시각 (epoch ms)
    memo         : Optional[str]  = None   # 사용자 메모. None 이면 "건드리지 않음" — 기존 메모를 지우지 않는다
