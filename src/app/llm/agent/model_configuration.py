from dataclasses import dataclass
from typing      import ClassVar
from typing      import Set
from typing      import Optional
from typing      import Dict
from typing      import Any

@dataclass(frozen = True, slots = True)
class ModelConfiguration:
    SUPPORTED_PROVIDER_SET    : ClassVar[Set[str]]       = {"openai", "anthropic", "ollama", "lm_studio", "vllm"}
    provider                  : str                              # openai | anthropic | ollama | lm_studio | vllm
    model_name                : str                              # 모델명
    api_key                   : Optional[str]            = None  # API 키 (기본값 : None)
    base_url                  : Optional[str]            = None  # 엔드포인트 URL (기본값 : None)
    temperature               : float                    = 0.0   # 온도 (기본값 : 0.0)
    maximum_token_count       : Optional[int]            = None  # 최대 토큰 수 (기본값 : None)
    timeout_second_count      : float                    = 120.0 # 요청 타임아웃(초) (기본값 : 120.0)
    maximum_retry_count       : int                      = 2     # 최대 재시도 횟수 (기본값 : 2)
    default_header_dictionary : Optional[Dict[str, str]] = None  # 커스텀 헤더 (vLLM 사내 인증 등) (기본값 : None)
    extra_body_dictionary     : Optional[Dict[str, Any]] = None  # OpenAI 호환 확장 바디 (vLLM 전용 파라미터) (기본값 : None)
    reasoning_enabled         : Optional[bool]           = None  # 추론(thinking) 모드 : False=끔(지연 최소화), True=켬, None=모델 기본값 (현재 ollama 전용)
    context_token_count       : Optional[int]            = None  # 컨텍스트 윈도우(num_ctx, ollama 전용) : 미설정 시 Ollama 기본 4096 — deepagents 시스템 프롬프트+히스토리가 이를 초과하면 프롬프트가 절단된다

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ValueError("MODEL PROVIDER IS REQUIRED : provider")
        if not isinstance(self.model_name, str) or not self.model_name.strip():
            raise ValueError("MODEL NAME IS REQUIRED : model_name")
        object.__setattr__(self, "provider", self.provider.strip().lower())
        object.__setattr__(self, "model_name", self.model_name.strip())
        object.__setattr__(self, "api_key", self.api_key.strip() if self.api_key else None)
        object.__setattr__(self, "base_url", self.base_url.strip() if self.base_url else None)
        if self.provider not in self.SUPPORTED_PROVIDER_SET:
            raise ValueError(f"UNSUPPORTED MODEL PROVIDER : {self.provider}")
        if self.temperature < 0.0:
            raise ValueError(f"INVALID MODEL TEMPERATURE : {self.temperature}")
        if self.maximum_token_count is not None and self.maximum_token_count <= 0:
            raise ValueError(f"INVALID MAXIMUM TOKEN COUNT : {self.maximum_token_count}")
        if self.context_token_count is not None and self.context_token_count <= 0:
            raise ValueError(f"INVALID CONTEXT TOKEN COUNT : {self.context_token_count}")
        if self.timeout_second_count <= 0.0:
            raise ValueError(f"INVALID MODEL TIMEOUT : {self.timeout_second_count}")
        if self.maximum_retry_count < 0:
            raise ValueError(f"INVALID MAXIMUM RETRY COUNT : {self.maximum_retry_count}")
        if self.provider == "vllm" and self.base_url is None:
            raise ValueError("VLLM BASE URL IS REQUIRED : base_url")
        if self.default_header_dictionary is not None and not isinstance(self.default_header_dictionary, dict):
            raise ValueError("INVALID DEFAULT HEADER DICTIONARY : default_header_dictionary")
        if self.extra_body_dictionary is not None and not isinstance(self.extra_body_dictionary, dict):
            raise ValueError("INVALID EXTRA BODY DICTIONARY : extra_body_dictionary")
