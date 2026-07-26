from typing import Any
from typing import Dict
from typing import Optional

from pydantic import BaseModel


class ParameterSet(BaseModel):
    temperature : Optional[float]           = None
    top_p : Optional[float]                 = None
    max_completion_tokens : Optional[int]   = None
    num_return_sequences : Optional[int]    = None
    timeout : Optional[int]                 = None
    max_retries : Optional[int]             = None
    stream_usage : Optional[bool]           = None
    default_headers : Optional[Dict[str, Any]] = None
    extra_body : Optional[Dict[str, Any]]   = None


class ModelPreset(BaseModel):
    name : str
    temperature : float
    top_p : float
    max_completion_tokens : int
    timeout : int
    max_retries : int
    stream_usage : bool
    default_headers : Dict[str, Any]
    extra_body : Dict[str, Any]
    num_return_sequences : int
    thinking : Optional[ParameterSet]       = None
    answer : Optional[ParameterSet]         = None


class ModelPresetsResponse(BaseModel):
    presets : Dict[str, ModelPreset]
    available_preset_names : list[str]
