from pydantic import BaseModel
from typing   import Dict
from typing   import Any
from typing   import List

class TimelineResponse(BaseModel):
    job                   : Dict[str, Any]
    task_list             : List[Dict[str, Any]]
    chunk_list            : List[Dict[str, Any]]
    unassigned_chunk_list : List[Dict[str, Any]]
    through_sequence      : int
    is_terminal           : bool
    next_after_sequence   : int
