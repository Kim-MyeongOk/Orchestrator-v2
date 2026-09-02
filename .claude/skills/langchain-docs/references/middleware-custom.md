# Middleware - Custom

원문 : https://docs.langchain.com/oss/python/langchain/middleware/custom

에이전트 실행 흐름의 특정 지점에서 실행되는 훅을 구현해 커스텀 미들웨어를 만든다.

## 훅

### 노드 스타일 훅 (순차 실행)

로깅/검증/상태 업데이트용. 특정 실행 지점에서 순차 실행.

| 훅 | 실행 시점 |
|---|---|
| `before_agent` | 에이전트 시작 전 (호출당 1회) |
| `before_model` | 각 모델 호출 전 |
| `after_model` | 각 모델 응답 후 |
| `after_agent` | 에이전트 완료 후 (호출당 1회) |

### 랩 스타일 훅 (호출 감싸기)

재시도/캐싱/변환용. 핸들러를 0번(단락)/1번(정상)/여러번(재시도) 호출할지 제어.

| 훅 | 실행 시점 |
|---|---|
| `wrap_model_call` | 각 모델 호출 주위 |
| `wrap_tool_call` | 각 도구 호출 주위 |

```python
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse

@wrap_model_call
def retry_model(request: ModelRequest, handler) -> ModelResponse:
    for attempt in range(3):
        try:
            return handler(request)
        except Exception as e:
            if attempt == 2:
                raise
            print(f"Retry {attempt + 1}/3 after error: {e}")
```

## 상태 업데이트

- **노드 스타일** : dict를 직접 반환 → 그래프 reducer로 상태에 적용.
- **랩 스타일** : 모델 호출은 `ExtendedModelResponse`(`Command` 포함)를 반환, 도구 호출은
  `Command`를 직접 반환. 요약 트리거 지점, 사용량 메타데이터 등 호출 중 계산된 필드 추적에 사용.

```python
from langchain.agents.middleware import ExtendedModelResponse
from langgraph.types import Command

@wrap_model_call(state_schema=UsageTrackingState)
def track_usage(request: ModelRequest, handler) -> ExtendedModelResponse:
    response = handler(request)
    return ExtendedModelResponse(
        model_response=response,
        command=Command(update={"last_model_call_tokens": 150}),
    )
```

### 다중 미들웨어 조합

- 명령은 reducer를 통해 적용됨(메시지는 가산적).
- 충돌 시 outer 우선(비-reducer 필드는 inner→outer 순, 최외곽 값 우선).
- 재시도 안전 : outer가 `handler()`를 재호출하면 이전 호출의 명령은 폐기됨.

## 미들웨어 생성 방법

### 데코레이터 기반 (단순)

단일 훅, 복잡한 설정 불필요, 빠른 프로토타이핑에 적합. 데코레이터 :
`@before_agent`, `@before_model`, `@after_model`, `@after_agent`, `@wrap_model_call`,
`@wrap_tool_call`, `@dynamic_prompt`.

```python
@before_model
def log_before_model(state: AgentState, runtime) -> dict | None:
    print(f"About to call model with {len(state['messages'])} messages")
    return None

agent = create_agent(model="gpt-5.4", middleware=[log_before_model, retry_model], tools=[...])
```

### 클래스 기반 (강력)

다중 훅, sync/async 둘 다 구현, 복잡한 설정, 재사용에 적합.

```python
from langchain.agents.middleware import AgentMiddleware

class LoggingMiddleware(AgentMiddleware):
    def before_model(self, state, runtime) -> dict | None:
        print(f"...{len(state['messages'])} messages")
        return None
    def after_model(self, state, runtime) -> dict | None:
        return None
    async def abefore_model(self, state, runtime) -> dict | None:  # async 버전
        return None
```

## 커스텀 상태 스키마

훅 간 상태 추적이 필요하면 `AgentState`를 확장한다. 카운터/플래그 유지, 훅 간 데이터 공유,
교차 관심사(rate limit/사용량 추적/감사 로깅) 구현, 조건부 결정에 사용.

```python
from langchain.agents.middleware import AgentState, before_model, after_model
from typing_extensions import NotRequired

class CustomState(AgentState):
    model_call_count: NotRequired[int]
    user_id: NotRequired[str]

@before_model(state_schema=CustomState, can_jump_to=["end"])
def check_call_limit(state: CustomState, runtime) -> dict | None:
    if state.get("model_call_count", 0) > 10:
        return {"jump_to": "end"}
    return None

@after_model(state_schema=CustomState)
def increment_counter(state: CustomState, runtime) -> dict | None:
    return {"model_call_count": state.get("model_call_count", 0) + 1}
```

## 실행 순서

`middleware=[m1, m2, m3]` 일 때 :
- `before_*` 훅 : 처음→마지막 (m1 → m2 → m3)
- `after_*` 훅 : 마지막→처음 (역순, m3 → m2 → m1)
- `wrap_*` 훅 : 중첩 (m1이 나머지 모두를 감쌈)

순서 : before_agent들 → [루프: before_model들 → wrap_model_call 중첩 → model → after_model
역순] → after_agent 역순.

## 에이전트 점프 (조기 종료)

`jump_to`가 담긴 dict 반환. 타깃 : `'end'`(종료), `'tools'`(도구 노드), `'model'`(모델 노드).
`@hook_config(can_jump_to=[...])`로 허용 타깃 선언.

```python
from langchain.agents.middleware import after_model, hook_config

@after_model
@hook_config(can_jump_to=["end"])
def check_for_blocked(state: AgentState, runtime) -> dict | None:
    if "BLOCKED" in state["messages"][-1].content:
        return {"messages": [AIMessage("I cannot respond to that request.")], "jump_to": "end"}
    return None
```

## 베스트 프랙티스

1. 미들웨어는 하나의 일에 집중. 2. 에러를 우아하게 처리(미들웨어 에러가 에이전트를 crash시키지
않게). 3. 적절한 훅 타입 사용(순차 로직은 노드, 제어 흐름은 랩). 4. 커스텀 상태 프로퍼티 문서화.
5. 통합 전 독립 유닛 테스트. 6. 실행 순서 고려(중요 미들웨어를 앞에). 7. 가능하면 프리빌트 사용.

## 예제

### 동적 프롬프트

`ModelRequest.system_message`(항상 `SystemMessage` 객체)를 읽고 수정. `content_blocks`로 접근해
블록 추가.

```python
@wrap_model_call
def add_context(request: ModelRequest, handler) -> ModelResponse:
    new_content = list(request.system_message.content_blocks) + [
        {"type": "text", "text": "Additional context."}
    ]
    return handler(request.override(system_message=SystemMessage(content=new_content)))
```

### 동적 모델 선택

```python
@wrap_model_call
def dynamic_model(request: ModelRequest, handler) -> ModelResponse:
    model = complex_model if len(request.messages) > 10 else simple_model
    return handler(request.override(model=model))
```

### 동적 도구 선택

```python
@wrap_model_call
def select_tools(request: ModelRequest, handler) -> ModelResponse:
    relevant_tools = select_relevant_tools(request.state, request.runtime)
    return handler(request.override(tools=relevant_tools))
# 모든 도구는 create_agent(tools=all_tools)로 사전 등록 필요
```

### 도구 호출 모니터링

```python
from langchain.tools.tool_node import ToolCallRequest

@wrap_tool_call
def monitor_tool(request: ToolCallRequest, handler) -> ToolMessage | Command:
    print(f"Executing tool: {request.tool_call['name']}, args: {request.tool_call['args']}")
    try:
        result = handler(request)
        return result
    except Exception as e:
        print(f"Tool failed: {e}")
        raise
```

### 프롬프트 캐싱 (Anthropic)

content blocks에 `cache_control` 디렉티브 추가.

```python
@wrap_model_call
def add_cached_context(request: ModelRequest, handler) -> ModelResponse:
    new_content = list(request.system_message.content_blocks) + [{
        "type": "text",
        "text": "Here is a large document...\n\n<document>...</document>",
        "cache_control": {"type": "ephemeral"},  # 이 지점까지 캐시됨
    }]
    return handler(request.override(system_message=SystemMessage(content=new_content)))
```
