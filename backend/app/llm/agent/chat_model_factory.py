import httpx

from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai                           import ChatOpenAI
from langchain_anthropic                        import ChatAnthropic
from langchain_ollama                           import ChatOllama
from langchain_google_genai                     import ChatGoogleGenerativeAI

from app.llm.agent.model_configuration import ModelConfiguration

class ChatModelFactory:
    # 생각 강도 → Gemini thinking_budget(토큰) 매핑
    GOOGLE_THINKING_BUDGET_DICTIONARY = {"low" : 1024, "medium" : 8192, "high" : 24576}
    @staticmethod
    def _create_openai_compatible_model(model_configuration : ModelConfiguration, default_base_url : Optional[str] = None, default_api_key : Optional[str] = None) -> BaseChatModel:
        # 스트리밍 중 usage 수신을 위해 stream_usage를 켠다. vLLM/LM Studio 버전에 따라 usage가 없을 수 있으므로 소비 측은 usage 부재를 허용한다.
        return ChatOpenAI(
            model                 = model_configuration.model_name,
            api_key               = model_configuration.api_key or default_api_key,
            base_url              = model_configuration.base_url or default_base_url,
            temperature           = model_configuration.temperature,
            max_completion_tokens = model_configuration.maximum_token_count,
            timeout               = model_configuration.timeout_second_count,
            max_retries           = model_configuration.maximum_retry_count,
            stream_usage          = True,
            default_headers       = model_configuration.default_header_dictionary,
            extra_body            = model_configuration.extra_body_dictionary
        )

    @staticmethod
    def create(model_configuration : ModelConfiguration) -> BaseChatModel:
        provider = model_configuration.provider.lower()
        if provider == "openai":
            return ChatModelFactory._create_openai_compatible_model(model_configuration)
        if provider == "anthropic":
            return ChatAnthropic(
                model       = model_configuration.model_name,
                api_key     = model_configuration.api_key,
                temperature = model_configuration.temperature,
                max_tokens  = model_configuration.maximum_token_count or 4096,
                timeout     = model_configuration.timeout_second_count,
                max_retries = model_configuration.maximum_retry_count
            )
        if provider == "google":
            # thinking_budget : Gemini 2.5+ 의 생각 강도 제어 (0 이면 생각 끔, None 이면 모델 기본)
            # include_thoughts : True 면 생각 요약이 응답에 포함되어 UI 로 스트리밍할 수 있다
            # Gemma 계열은 thinking 파라미터 자체를 지원하지 않으므로(전송 시 400) None 으로 두어 전송을 생략한다
            is_thinking_supported = not model_configuration.model_name.lower().startswith("gemma")
            thinking_budget       = None
            include_thoughts      = None
            if is_thinking_supported:
                if model_configuration.reasoning_effort is not None:
                    thinking_budget = ChatModelFactory.GOOGLE_THINKING_BUDGET_DICTIONARY[model_configuration.reasoning_effort]
                elif model_configuration.reasoning_enabled is False:
                    thinking_budget = 0
                include_thoughts = bool(model_configuration.reasoning_enabled)
            return ChatGoogleGenerativeAI(
                model             = model_configuration.model_name,
                google_api_key    = model_configuration.api_key,
                temperature       = model_configuration.temperature,
                max_output_tokens = model_configuration.maximum_token_count,
                thinking_budget   = thinking_budget,
                include_thoughts  = include_thoughts,
                timeout           = model_configuration.timeout_second_count,
                max_retries       = model_configuration.maximum_retry_count
            )
        if provider == "ollama":
            # reasoning : 생각 강도(low/medium/high, 모델이 지원할 때만 유효) > on/off(True/False) > 모델 기본(None) 순으로 적용
            # (thinking 이 켜져 있으면 짧은 답변에도 수천 토큰을 생성해 턴 지연이 분 단위로 커진다)
            #
            # 단, 카탈로그의 reasoning_enabled=False 는 "이 모델은 thinking 을 못 쓴다"는 선언이므로
            # 요청별 생각 강도가 이를 덮지 못하게 막는다. 덮으면 thinking 미지원 모델에
            # think 가 전송되어 400 ("...does not support thinking") 으로 턴이 통째로 실패한다.
            # think 를 false 로 보내는 것은 미지원 모델도 허용하므로 끄기는 항상 안전하다.
            if model_configuration.reasoning_enabled is False:
                reasoning_option = False
            else:
                reasoning_option = model_configuration.reasoning_effort or model_configuration.reasoning_enabled
            # 원격 ollama API(https://ollama.com)를 사용하는 경우 default_header_dictionary 에 Authorization 헤더를 포함한다
            client_kwargs = {"timeout" : model_configuration.timeout_second_count}
            if model_configuration.default_header_dictionary:
                client_kwargs["headers"] = model_configuration.default_header_dictionary
            return ChatOllama(
                model                = model_configuration.model_name,
                base_url             = model_configuration.base_url or "http://localhost:11434",
                temperature          = model_configuration.temperature,
                reasoning            = reasoning_option,
                num_ctx              = model_configuration.context_token_count,
                num_predict          = model_configuration.maximum_token_count,
                client_kwargs        = client_kwargs,
                sync_client_kwargs   = {"transport" : httpx.HTTPTransport(retries = model_configuration.maximum_retry_count)},
                async_client_kwargs  = {"transport" : httpx.AsyncHTTPTransport(retries = model_configuration.maximum_retry_count)}
            )
        if provider == "lm_studio":
            # LM Studio는 OpenAI 호환 서버이며 api_key는 더미 값을 사용한다
            return ChatModelFactory._create_openai_compatible_model(model_configuration, default_base_url = "http://localhost:1234/v1", default_api_key = "lm-studio")
        if provider == "vllm":
            # 사내 vLLM : base_url/api_key/default_headers/extra_body를 커스텀 설정으로 전달한다
            return ChatModelFactory._create_openai_compatible_model(model_configuration, default_api_key = "vllm")
        raise ValueError(f"UNSUPPORTED MODEL PROVIDER : {model_configuration.provider}")
