from pydantic import BaseModel
from typing   import List
from typing   import Dict
from typing   import Any
from typing   import Optional

class ThreadListResponse(BaseModel):
    thread_list : List[Dict[str, Any]]
    next_cursor : Optional[str] = None

class ThreadDetailResponse(BaseModel):
    thread       : Dict[str, Any]
    message_list : List[Dict[str, Any]]
    run_list     : List[Dict[str, Any]]
