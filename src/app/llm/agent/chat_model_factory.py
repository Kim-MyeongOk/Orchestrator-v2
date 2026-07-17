import httpx

from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai                           import ChatOpenAI
from langchain_anthropic                        import ChatAnthropic
from langchain_ollama                           import ChatOllama

from app.llm.agent.model_configuration import ModelConfiguration

class ChatModelFactory:
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
        if provider == "ollama":
            return ChatOllama(
                model                = model_configuration.model_name,
                base_url             = model_configuration.base_url or "http://localhost:11434",
                temperature          = model_configuration.temperature,
                num_predict          = model_configuration.maximum_token_count,
                client_kwargs        = {"timeout" : model_configuration.timeout_second_count},
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
