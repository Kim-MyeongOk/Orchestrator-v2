import uuid

from pydantic import BaseModel
from pydantic import ConfigDict
from typing   import Optional
from typing   import List
from pydantic import Field
from typing   import Literal

from app.llm.api.message_request        import MessageRequest
from app.llm.api.model_override_request import ModelOverrideRequest

class ChatRequest(BaseModel):
    model_config                                    = ConfigDict(extra = "forbid")
    thread_id     : Optional[uuid.UUID]             = None
    messages      : List[MessageRequest]            = Field(min_length = 1)
    output_format : Literal["deepagents", "openai"] = "deepagents"
    model         : Optional[ModelOverrideRequest]  = None
