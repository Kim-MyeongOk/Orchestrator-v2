# Agents

원문 : https://docs.langchain.com/oss/python/langchain/agents

에이전트는 언어 모델과 도구를 결합해, 작업을 추론하고 어떤 도구를 쓸지 결정하며 반복적으로 해결로
나아가는 시스템을 만든다. `create_agent`가 운영 준비된 구현을 제공한다. 에이전트는 모델이 최종
출력을 내거나 반복 한도에 도달할 때까지 도구를 루프로 실행한다.

`create_agent`는 LangGraph 위에 **그래프** 기반 에이전트 런타임을 만든다. 그래프는 노드(단계)와
엣지(연결)로 구성되며, 에이전트는 모델 노드/도구 노드/미들웨어 같은 노드를 실행하며 그래프를 따라
이동한다.

## 핵심 구성요소

### Model

#### Static model (정적)

생성 시 한 번 설정되어 실행 내내 유지. 가장 일반적.

```python
from langchain.agents import create_agent

agent = create_agent("openai:gpt-5.4", tools=tools)
```

모델 식별자 문자열은 자동 추론을 지원한다(`"gpt-5.4"` → `"openai:gpt-5.4"`). 더 세밀한 제어는
프로바이더 패키지로 인스턴스를 직접 생성한다.

```python
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

model = ChatOpenAI(model="gpt-5.4", temperature=0.1, max_tokens=1000, timeout=30)
agent = create_agent(model, tools=tools)
```

#### Dynamic model (동적)

런타임에 상태/컨텍스트에 따라 모델을 선택. `@wrap_model_call` 미들웨어로 요청의 모델을 수정한다.

```python
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse

@wrap_model_call
def dynamic_model_selection(request: ModelRequest, handler) -> ModelResponse:
    message_count = len(request.state["messages"])
    model = advanced_model if message_count > 10 else basic_model
    return handler(request.override(model=model))

agent = create_agent(model=basic_model, tools=tools, middleware=[dynamic_model_selection])
```

주의 : 구조화 출력 사용 시 pre-bound 모델(`bind_tools` 이미 호출됨)은 지원되지 않는다.

### Tools

에이전트는 단순 모델 바인딩을 넘어 연속/병렬 도구 호출, 동적 도구 선택, 재시도/에러 처리, 도구
호출 간 상태 영속을 가능하게 한다.

#### Static tools

```python
from langchain.tools import tool
from langchain.agents import create_agent

@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

agent = create_agent(model, tools=[search, get_weather])
```

빈 도구 리스트를 주면 도구 호출 능력이 없는 단일 LLM 노드가 된다.

#### Dynamic tools

런타임에 사용 가능한 도구 집합을 수정. 두 접근법이 있다.

**1) 사전 등록된 도구 필터링** — 모든 도구를 생성 시 알고 있을 때, 상태/권한/컨텍스트에 따라
노출 도구를 필터링한다. `wrap_model_call`에서 `request.override(tools=...)`로 처리.

```python
@wrap_model_call
def context_based_tools(request: ModelRequest, handler) -> ModelResponse:
    user_role = request.runtime.context.user_role
    if user_role == "admin":
        pass
    elif user_role == "editor":
        tools = [t for t in request.tools if t.name != "delete_data"]
        request = request.override(tools=tools)
    else:
        tools = [t for t in request.tools if t.name.startswith("read_")]
        request = request.override(tools=tools)
    return handler(request)
```

상태(`request.state`), Store(`request.runtime.store`), 런타임 컨텍스트(`request.runtime.context`)
기반 필터링이 모두 가능하다.

**2) 런타임 도구 등록** — MCP 서버 등에서 도구를 런타임에 발견/생성할 때. 두 훅이 필요하다 :
- `wrap_model_call` : 동적 도구를 요청에 추가
- `wrap_tool_call` : 동적으로 추가된 도구의 실행 처리 (없으면 에이전트가 실행 방법을 모름)

```python
class DynamicToolMiddleware(AgentMiddleware):
    def wrap_model_call(self, request: ModelRequest, handler):
        updated = request.override(tools=[*request.tools, calculate_tip])
        return handler(updated)

    def wrap_tool_call(self, request: ToolCallRequest, handler):
        if request.tool_call["name"] == "calculate_tip":
            return handler(request.override(tool=calculate_tip))
        return handler(request)
```

#### Tool error handling

`@wrap_tool_call`로 도구 에러를 커스텀 처리한다.

```python
from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage

@wrap_tool_call
def handle_tool_errors(request, handler):
    try:
        return handler(request)
    except Exception as e:
        return ToolMessage(
            content=f"Tool error: Please check your input and try again. ({str(e)})",
            tool_call_id=request.tool_call["id"]
        )
```

#### ReAct 루프

에이전트는 ReAct(Reasoning + Acting) 패턴을 따른다 : 간단한 추론 단계와 타깃 도구 호출을 번갈아
하며, 결과 관찰을 다음 결정에 반영해 최종 답을 낼 때까지 반복한다.

### System prompt

`system_prompt`는 `str` 또는 `SystemMessage`를 받는다. `SystemMessage`는 Anthropic 프롬프트
캐싱 같은 프로바이더별 기능에 유용하다.

```python
from langchain.messages import SystemMessage

agent = create_agent(
    model="google_genai:gemini-3.1-pro-preview",
    system_prompt=SystemMessage(content=[
        {"type": "text", "text": "You are an AI assistant..."},
        {"type": "text", "text": "<large content>", "cache_control": {"type": "ephemeral"}},
    ])
)
```

#### Dynamic system prompt

`@dynamic_prompt` 미들웨어로 런타임 컨텍스트/상태에 따라 프롬프트를 생성한다.

```python
from langchain.agents.middleware import dynamic_prompt, ModelRequest

@dynamic_prompt
def user_role_prompt(request: ModelRequest) -> str:
    user_role = request.runtime.context.get("user_role", "user")
    base = "You are a helpful assistant."
    if user_role == "expert":
        return f"{base} Provide detailed technical responses."
    return base
```

### Name

멀티 에이전트에서 서브그래프 노드 식별자로 쓰인다. `snake_case`를 권장한다(공백/특수문자는 일부
프로바이더가 거부). 도구명도 동일.

```python
agent = create_agent(model, tools, name="research_assistant")
```

## 호출 (Invocation)

상태 업데이트(새 메시지)를 전달해 호출한다.

```python
result = agent.invoke({"messages": [{"role": "user", "content": "..."}]})
```

LangGraph Graph API를 따르므로 `stream`/`invoke` 등 모든 메서드를 지원한다.

## 고급 개념

### Structured output

`response_format` 파라미터로 특정 형식 출력을 받는다.

- **ToolStrategy** : 인공 도구 호출로 구조화 출력 생성. 도구 호출 지원 모델이면 작동.
- **ProviderStrategy** : 프로바이더 네이티브 구조화 출력. 더 신뢰성 높지만 지원 프로바이더만.

```python
from pydantic import BaseModel
from langchain.agents.structured_output import ToolStrategy, ProviderStrategy

class ContactInfo(BaseModel):
    name: str
    email: str

agent = create_agent(model="gpt-5.4-mini", tools=[search_tool],
                     response_format=ToolStrategy(ContactInfo))
result["structured_response"]  # ContactInfo(...)
```

langchain 1.0부터 스키마만 전달하면(`response_format=ContactInfo`) 네이티브 지원 시
`ProviderStrategy`, 아니면 `ToolStrategy`로 폴백한다.

### Memory

메시지 상태로 대화 히스토리를 자동 유지(단기 메모리). 커스텀 상태는 `AgentState`를 확장한
`TypedDict`여야 한다(langchain 1.0부터 Pydantic/dataclass 미지원).

**미들웨어로 정의 (선호)** :

```python
from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware

class CustomState(AgentState):
    user_preferences: dict

class CustomMiddleware(AgentMiddleware):
    state_schema = CustomState
    tools = [tool1, tool2]

    def before_model(self, state: CustomState, runtime) -> dict | None:
        ...
```

**`state_schema`로 정의 (도구에서만 쓸 때 단축)** :

```python
agent = create_agent(model, tools=[tool1, tool2], state_schema=CustomState)
```

### Streaming

`agent.stream(..., stream_mode="values")`로 중간 진행을 스트리밍한다. 각 chunk는 그 시점의 전체
상태를 담는다.

### Middleware

실행 단계별로 에이전트 동작을 커스터마이즈한다 : 모델 호출 전 상태 처리, 응답 수정/검증(가드레일),
도구 에러 처리, 동적 모델 선택, 로깅/모니터링. `@before_model`, `@after_model`, `@wrap_tool_call`
등의 데코레이터가 있다.
