from pydantic import BaseModel
from pydantic import ConfigDict
from typing   import Optional
from typing   import Literal
from pydantic import Field
from typing   import Dict
from typing   import Any
from pydantic import model_validator

class ModelOverrideRequest(BaseModel):
    model_config                                                                                        = ConfigDict(extra = "forbid")
    provider                  : Optional[Literal["openai", "anthropic", "ollama", "lm_studio", "vllm"]] = None
    model_name                : Optional[str]                                                           = Field(default = None, min_length = 1)
    api_key                   : Optional[str]                                                           = None
    base_url                  : Optional[str]                                                           = None
    temperature               : Optional[float]                                                         = Field(default = None, ge = 0.0)
    maximum_token_count       : Optional[int]                                                           = Field(default = None, ge = 1)
    timeout_second_count      : Optional[float]                                                         = Field(default = None, gt = 0.0)
    maximum_retry_count       : Optional[int]                                                           = Field(default = None, ge = 0)
    default_header_dictionary : Optional[Dict[str, str]]                                                = None
    extra_body_dictionary     : Optional[Dict[str, Any]]                                                = None

    @model_validator(mode = "after")
    def validate_provider_override(self) -> "ModelOverrideRequest":
        if self.provider is not None and self.model_name is None:
            raise ValueError("MODEL NAME IS REQUIRED WHEN PROVIDER IS OVERRIDDEN : model_name")
        return self
