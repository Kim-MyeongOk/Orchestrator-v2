# Messages

원문 : https://docs.langchain.com/oss/python/langchain/messages

메시지는 LangChain에서 모델 컨텍스트의 기본 단위다. 모델의 입출력을 나타내며 콘텐츠와 메타데이터를
담는다. 구성요소 : **Role**(메시지 타입), **Content**(텍스트/이미지/오디오/문서 등),
**Metadata**(응답 정보, 메시지 ID, 토큰 사용량 등). 모든 프로바이더에서 동작하는 표준 메시지 타입.

## 기본 사용

```python
from langchain.messages import HumanMessage, AIMessage, SystemMessage

messages = [
    SystemMessage("You are a helpful assistant."),
    HumanMessage("Hello, how are you?"),
]
response = model.invoke(messages)  # AIMessage 반환
```

세 가지 입력 형식 : 텍스트 문자열, 메시지 객체 리스트, 딕셔너리 형식(OpenAI chat completions).

```python
# 딕셔너리 형식
messages = [
    {"role": "system", "content": "You are a poetry expert"},
    {"role": "user", "content": "Write a haiku about spring"},
    {"role": "assistant", "content": "Cherry blossoms bloom..."},
]
```

## 메시지 타입

### SystemMessage

모델 동작을 프라이밍하는 초기 지시. 톤/역할/가이드라인 설정.

### HumanMessage

사용자 입력. 텍스트/이미지/오디오/파일 등 멀티모달 콘텐츠 포함 가능. 문자열은 단일
`HumanMessage`의 단축형. 메타데이터(`name`, `id`) 추가 가능(`name`은 프로바이더마다 처리 다름).

### AIMessage

모델 호출 출력. 멀티모달 데이터, 도구 호출, 프로바이더별 메타데이터 포함. 대화 히스토리용으로
수동 생성도 가능.

주요 속성 : `text`, `content`(원시), `content_blocks`(표준화), `tool_calls`, `id`,
`usage_metadata`, `response_metadata`.

```python
# 도구 호출
response = model_with_tools.invoke("What's the weather in Paris?")
for tc in response.tool_calls:
    print(tc["name"], tc["args"], tc["id"])

# 토큰 사용량
response.usage_metadata
# {'input_tokens': 8, 'output_tokens': 304, 'total_tokens': 312,
#  'input_token_details': {'audio': 0, 'cache_read': 0},
#  'output_token_details': {'audio': 0, 'reasoning': 256}}

# 스트리밍 chunk 합산
full_message = None
for chunk in model.stream("Hi"):   # AIMessageChunk
    full_message = chunk if full_message is None else full_message + chunk
```

### ToolMessage

단일 도구 실행 결과를 모델에 전달. `tool_call_id`가 `AIMessage`의 도구 호출 ID와 일치해야 한다.

```python
from langchain.messages import ToolMessage

tool_message = ToolMessage(
    content="Sunny, 72°F",
    tool_call_id="call_123",  # 호출 ID와 일치
    name="get_weather",
)
messages = [HumanMessage("..."), ai_message, tool_message]
response = model.invoke(messages)
```

속성 : `content`(필수, 문자열화된 출력), `tool_call_id`(필수), `name`(필수), `artifact`(모델에
전송되지 않지만 프로그램적으로 접근 가능한 부가 데이터 — 원시 결과/디버깅/다운스트림 처리에 유용,
예: retrieval 메타데이터).

## 메시지 콘텐츠

`content` 속성은 느슨한 타입(문자열 또는 비타입 객체 리스트). 다음 중 하나를 담는다 :
1. 문자열
2. 프로바이더 네이티브 포맷 content block 리스트
3. LangChain 표준 content block 리스트

```python
# 표준 content blocks (타입 안전 인터페이스)
human_message = HumanMessage(content_blocks=[
    {"type": "text", "text": "Hello"},
    {"type": "image", "url": "https://example.com/image.jpg"},
])
```

`content_blocks` 지정 시 `content`도 함께 채워진다.

### Standard content blocks

`content_blocks` 프로퍼티는 `content`를 표준화된 타입 안전 표현으로 lazy 파싱한다. Anthropic의
`thinking`이나 OpenAI의 `reasoning`이 일관된 `ReasoningContentBlock`으로 파싱된다.

LangChain 외부 앱에서 표준 표현이 필요하면 `LC_OUTPUT_VERSION=v1` 환경변수 또는
`init_chat_model("...", output_version="v1")`로 content blocks를 content에 저장하도록 opt-in.

### Multimodal

이미지/PDF/오디오/비디오를 content block으로 입력. URL / base64(+ `mime_type`) /
프로바이더 관리 `file_id` 방식 지원.

```python
message = {
    "role": "user",
    "content": [
        {"type": "text", "text": "Describe this image."},
        {"type": "image", "url": "https://example.com/image.jpg"},
        # 또는 {"type": "image", "base64": "...", "mime_type": "image/jpeg"}
        # 또는 {"type": "image", "file_id": "file-abc123"}
    ]
}
```

타입 : `image`, `file`(PDF 등), `audio`, `video`. 모델마다 지원 포맷/크기 한도 다름.

### Content block 타입 레퍼런스

- **Core** : `TextContentBlock`(`text`), `ReasoningContentBlock`(`reasoning`).
- **Multimodal** : `ImageContentBlock`, `AudioContentBlock`, `VideoContentBlock`,
  `FileContentBlock`, `PlainTextContentBlock`(`text-plain`, `.txt`/`.md`).
- **Tool Calling** : `ToolCall`(`tool_call`), `ToolCallChunk`(`tool_call_chunk`, 스트리밍 조각,
  `index` 포함), `InvalidToolCall`(`invalid_tool_call`, JSON 파싱 오류).
- **Server-Side Tool** : `ServerToolCall`, `ServerToolCallChunk`, `ServerToolResult`
  (`status`: `"success"`/`"error"`).
- **Provider-Specific** : `NonStandardContentBlock`(`non_standard`, `value`에 프로바이더 데이터).

content blocks는 v1에서 도입된 새 프로퍼티로, `content`를 대체하지 않고 표준 포맷 접근을 제공한다.
