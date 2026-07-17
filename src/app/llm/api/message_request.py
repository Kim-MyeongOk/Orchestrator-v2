from pydantic import BaseModel
from pydantic import ConfigDict
from typing   import Literal
from typing   import Union
from typing   import List
from typing   import Dict
from typing   import Any
from typing   import Optional

class MessageRequest(BaseModel):
    model_config                                  = ConfigDict(extra = "forbid")
    role         : Literal["system", "user", "assistant", "tool"]
    content      : Union[str, List[Dict[str, Any]]]
    name         : Optional[str]                  = None
    tool_call_id : Optional[str]                  = None
    tool_calls   : Optional[List[Dict[str, Any]]] = None
