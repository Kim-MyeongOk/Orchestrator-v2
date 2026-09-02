# Models

원문 : https://docs.langchain.com/oss/python/langchain/models

모델은 에이전트의 추론 엔진이다. 텍스트 생성 외에 도구 호출, 구조화 출력, 멀티모달, 추론을
지원한다. LangChain의 표준 모델 인터페이스로 프로바이더 간 전환이 쉽다.

## 기본 사용

두 가지 방식 : (1) 에이전트와 함께, (2) 단독 호출(텍스트 생성/분류/추출).

### 모델 초기화

```python
from langchain.chat_models import init_chat_model

model = init_chat_model("claude-sonnet-4-6")          # init 헬퍼
# 또는 클래스 직접
from langchain_anthropic import ChatAnthropic
model = ChatAnthropic(model="claude-sonnet-4-6")

response = model.invoke("Why do parrots talk?")
```

프로바이더 패키지는 모델명을 프로바이더 API에 그대로 넘기므로, 신규 모델명은 LangChain 업데이트
없이 즉시 작동한다.

## 파라미터

표준 파라미터 : `model`(필수, `"{provider}:{model}"` 형식 가능), `api_key`, `temperature`,
`max_tokens`, `timeout`, `max_retries`(기본 6).

```python
model = init_chat_model(
    "claude-sonnet-4-6",
    temperature=0.7,
    timeout=30,
    max_tokens=1000,
    max_retries=6,
)
```

### 연결 복원력 (Connection resilience)

실패한 API 요청을 지수 백오프로 자동 재시도. 기본 최대 6회(네트워크 에러, 429, 5xx). 401/404
같은 클라이언트 에러는 재시도하지 않음. 불안정한 네트워크의 장시간 에이전트 작업에는 `max_retries`
10~15 + checkpointer 권장.

## 호출 (Invocation)

### invoke

단일 메시지 또는 메시지 리스트(대화 히스토리)를 입력.

```python
conversation = [
    {"role": "system", "content": "You translate English to French."},
    {"role": "user", "content": "Translate: I love programming."},
]
response = model.invoke(conversation)  # AIMessage(...)
```

문자열 반환이면 채팅 모델이 아닌 레거시 텍스트 완성 LLM이다(채팅 모델은 `Chat` 접두사).

### stream

생성되는 대로 chunk를 yield. `invoke`가 단일 `AIMessage`를 반환하는 반면 `stream`은 여러
`AIMessageChunk`를 반환하며, **합산으로 전체 메시지를 구성**할 수 있다.

```python
for chunk in model.stream("Why do parrots have colorful feathers?"):
    print(chunk.text, end="|", flush=True)

# chunk 합산으로 전체 메시지 구성
full = None
for chunk in model.stream("..."):
    full = chunk if full is None else full + chunk
print(full.content_blocks)
```

content block별 처리(추론/도구 호출 청크/텍스트 구분) :

```python
for chunk in model.stream("..."):
    for block in chunk.content_blocks:
        if block["type"] == "reasoning":
            ...
        elif block["type"] == "tool_call_chunk":
            ...
        elif block["type"] == "text":
            print(block["text"])
```

**Auto-streaming** : LangGraph 노드에서 `model.invoke()`를 호출해도 전체 앱이 스트리밍 모드면
LangChain이 자동으로 내부 스트리밍으로 위임해 콜백 이벤트(`on_llm_new_token`)를 발생시킨다.

### batch

독립적 요청들을 클라이언트 측에서 병렬 처리(프로바이더 batch API와는 다름).

```python
responses = model.batch(["q1", "q2", "q3"])
# 완료 순서대로 받기 (순서 뒤섞일 수 있음, 입력 인덱스 포함)
for response in model.batch_as_completed(["q1", "q2", "q3"]):
    print(response)

# 병렬 호출 수 제한
model.batch(inputs, config={"max_concurrency": 5})
```

## Tool calling

도구를 `bind_tools`로 바인딩하면 모델이 호출을 **요청**한다(실행은 에이전트 또는 사용자 몫).

```python
from langchain.tools import tool

@tool
def get_weather(location: str) -> str:
    """Get the weather at a location."""
    return f"It's sunny in {location}."

model_with_tools = model.bind_tools([get_weather])
response = model_with_tools.invoke("What's the weather in Boston?")
for tc in response.tool_calls:
    print(tc["name"], tc["args"])
```

- **도구 실행 루프** : 모델 호출 → 도구 실행 → `ToolMessage`(`tool_call_id` 매칭) 추가 → 재호출.
- **강제 호출** : `bind_tools([t], tool_choice="any")` 또는 `tool_choice="tool_name"`.
- **병렬 호출** : 다수 모델이 기본 지원. 끄려면 `parallel_tool_calls=False`.
- **스트리밍 도구 호출** : `ToolCallChunk`로 점진적 구성. `chunk.tool_call_chunks` 누적.

## Structured output

`with_structured_output`으로 스키마에 맞는 출력을 강제한다. Pydantic / TypedDict / JSON Schema 지원.

```python
from pydantic import BaseModel, Field

class Movie(BaseModel):
    title: str = Field(description="The title")
    year: int

model_with_structure = model.with_structured_output(Movie)
response = model_with_structure.invoke("Details about Inception")  # Movie(...)
```

- `method` : `'json_schema'`(프로바이더 전용 기능), `'function_calling'`(도구 호출로 유도),
  `'json_mode'`(JSON 생성, 스키마는 프롬프트에 명시).
- `include_raw=True` : 파싱된 출력 + 원본 `AIMessage`를 함께 반환(`{"raw":..., "parsed":...,
  "parsing_error":...}`). 토큰 카운트 등 메타데이터 접근에 유용.
- Pydantic은 자동 검증, TypedDict/JSON Schema는 수동 검증.

## 고급 주제

### Model profiles (langchain>=1.1)

`.profile` 속성으로 지원 기능/용량을 노출(models.dev 기반). 컨텍스트 윈도우 크기, 멀티모달,
도구 호출 지원 여부 등. 요약 미들웨어 트리거나 구조화 출력 전략 추론에 활용. (beta, 포맷 변경 가능)

```python
model.profile  # {"max_input_tokens": 400000, "tool_calling": True, ...}
model = init_chat_model("...", profile=custom_profile)  # 직접 지정
```

### Multimodal

이미지/오디오/비디오를 content blocks로 입출력. 크로스 프로바이더 표준 포맷, OpenAI chat
completions 포맷, 프로바이더 네이티브 포맷 모두 지원.

```python
response = model.invoke("Create a picture of a cat")
# [{"type": "text", ...}, {"type": "image", "base64": "...", "mime_type": "image/jpeg"}]
```

### Reasoning

다단계 추론 과정을 노출. content block의 `"reasoning"` 타입으로 접근. 모델에 따라 추론 effort
("low"/"high") 또는 토큰 예산 지정 가능, 비활성화도 가능.

### Local models

자체 하드웨어에서 로컬 실행(데이터 프라이버시, 커스텀 모델, 비용 절감). Ollama가 가장 쉬운 방법.

### Prompt caching

세 단계 : (1) 암묵적 프로바이더 캐싱(설정 불필요, OpenAI/Gemini), (2) 프로바이더 명시적
제어(`prompt_cache_key`, Anthropic `cache_control`, Bedrock `cachePoint`), (3) LangChain
미들웨어(`AnthropicPromptCachingMiddleware`, `BedrockPromptCachingMiddleware`). 캐시 사용량은
응답의 usage metadata에 반영.

### Server-side tool use

프로바이더가 서버 측 도구 호출 루프 지원(웹 검색, 코드 인터프리터). 단일 대화 턴에서 호출/결과가
content blocks(`server_tool_call`, `server_tool_result`)로 반환. 별도 `ToolMessage` 불필요.

```python
model_with_tools = model.bind_tools([{"type": "web_search"}])
response = model_with_tools.invoke("...")
print(response.content_blocks)
```

### Rate limiting

`rate_limiter` 파라미터로 요청 속도 제어. 내장 `InMemoryRateLimiter`(스레드 안전).

```python
from langchain_core.rate_limiters import InMemoryRateLimiter

rate_limiter = InMemoryRateLimiter(
    requests_per_second=0.1, check_every_n_seconds=0.1, max_bucket_size=10
)
model = init_chat_model(model="gpt-5.5", model_provider="openai", rate_limiter=rate_limiter)
```

### Base URL / proxy (vLLM 등 OpenAI 호환 API)

OpenAI 호환 API(vLLM, Together AI 등)는 `base_url`로 사용.

```python
model = init_chat_model(
    model="MODEL_NAME",
    model_provider="openai",
    base_url="BASE_URL",
    api_key="YOUR_API_KEY",
)
```

주의 : `model_provider="openai"`는 공식 OpenAI 스펙을 타깃하므로 라우터/프록시의 프로바이더별
필드는 보존되지 않을 수 있음. OpenRouter/LiteLLM은 전용 통합(`ChatOpenRouter`,
`ChatLiteLLM`) 권장. HTTP 프록시는 `ChatOpenAI(..., openai_proxy="http://...")`.

### Log probabilities

```python
model = init_chat_model(model="gpt-5.5", model_provider="openai").bind(logprobs=True)
response = model.invoke("...")
print(response.response_metadata["logprobs"])
```

### Token usage

프로바이더가 반환하면 `AIMessage`에 포함. 집계는 콜백 또는 컨텍스트 매니저로 추적.

```python
from langchain_core.callbacks import UsageMetadataCallbackHandler, get_usage_metadata_callback

# 콜백 핸들러
callback = UsageMetadataCallbackHandler()
model.invoke("Hello", config={"callbacks": [callback]})
print(callback.usage_metadata)

# 컨텍스트 매니저
with get_usage_metadata_callback() as cb:
    model.invoke("Hello")
    print(cb.usage_metadata)
# {'gpt-5.4-mini': {'input_tokens': 8, 'output_tokens': 10, 'total_tokens': 18,
#   'input_token_details': {'audio': 0, 'cache_read': 0}, ...}}
```

주의 : OpenAI/Azure OpenAI chat completions는 스트리밍 시 토큰 사용량 수신에 opt-in 필요
(`stream_options={"include_usage": True}` 패턴).

### Invocation config (RunnableConfig)

```python
response = model.invoke("Tell me a joke", config={
    "run_name": "joke_generation",
    "tags": ["humor", "demo"],
    "metadata": {"user_id": "123"},
    "callbacks": [my_callback_handler],
})
```

`run_name`, `tags`, `metadata`, `max_concurrency`, `callbacks`, `recursion_limit` 등.

### Configurable models

런타임에 모델/파라미터를 교체.

```python
configurable_model = init_chat_model(temperature=0)
configurable_model.invoke("...", config={"configurable": {"model": "gpt-5-nano"}})
configurable_model.invoke("...", config={"configurable": {"model": "claude-sonnet-4-6"}})

# 기본값 + 설정 가능 필드 + 프리픽스
first_model = init_chat_model(
    model="gpt-5.4-mini", temperature=0,
    configurable_fields=("model", "model_provider", "temperature", "max_tokens"),
    config_prefix="first",
)
```

`bind_tools`, `with_structured_output` 등 선언적 연산을 configurable 모델에도 적용 가능.

### Dynamic model selection

`@wrap_model_call` 미들웨어로 런타임 상태/컨텍스트에 따라 모델 선택(라우팅/비용 최적화). 구조화
출력 사용 시 pre-bound 모델은 미지원.
