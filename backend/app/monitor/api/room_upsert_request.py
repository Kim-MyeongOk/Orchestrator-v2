from typing import Optional

from pydantic import BaseModel


class RoomUpsertRequest(BaseModel):
    user_id          : str
    room_id          : str
    thread_id        : str
    title            : str            = "새 대화"
    model            : Optional[str]  = None
    reasoning_effort : Optional[str]  = None
