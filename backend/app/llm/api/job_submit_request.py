from pydantic import ConfigDict
from typing   import Optional
from pydantic import Field

from app.llm.api.chat_request import ChatRequest

class JobSubmitRequest(ChatRequest):
    model_config                    = ConfigDict(extra = "forbid")
    idempotency_key : Optional[str] = Field(default = None, min_length = 1, max_length = 200)

