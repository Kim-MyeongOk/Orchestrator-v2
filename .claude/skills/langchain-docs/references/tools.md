# Tools

원문 : https://docs.langchain.com/oss/python/langchain/tools

도구는 에이전트가 실시간 데이터 조회, 코드 실행, 외부 DB 질의, 행동을 할 수 있게 한다. 내부적으로
잘 정의된 입출력을 가진 호출 가능 함수이며, 모델이 대화 컨텍스트에 따라 호출 시점과 인자를 결정한다.

## 도구 생성

### 기본 정의

`@tool` 데코레이터를 사용한다. 함수의 docstring이 도구 설명이 되어 모델이 사용 시점을 이해하는 데
쓰인다. **타입 힌트는 필수**(입력 스키마를 정의). 이름은 `snake_case` 권장(공백/특수문자는 일부
프로바이더가 거부).

```python
from langchain.tools import tool

@tool
def search_database(query: str, limit: int = 10) -> str:
    """Search the customer database for records matching the query.

    Args:
        query: Search terms to look for
        limit: Maximum number of results to return
    """
    return f"Found {limit} results for '{query}'"
```

### 도구 속성 커스터마이즈

```python
@tool("web_search")  # 커스텀 이름
def search(query: str) -> str:
    """Search the web for information."""
    return f"Results for: {query}"

@tool("calculator", description="Performs arithmetic calculations.")
def calc(expression: str) -> str:
    """Evaluate mathematical expressions."""
    return str(eval(expression))
```

### 고급 스키마 (Pydantic / JSON Schema)

```python
from pydantic import BaseModel, Field
from typing import Literal

class WeatherInput(BaseModel):
    """Input for weather queries."""
    location: str = Field(description="City name or coordinates")
    units: Literal["celsius", "fahrenheit"] = Field(default="celsius")
    include_forecast: bool = Field(default=False)

@tool(args_schema=WeatherInput)
def get_weather(location: str, units: str = "celsius", include_forecast: bool = False) -> str:
    """Get current weather and optional forecast."""
    ...
```

### 예약된 인자 이름

`config`(내부 `RunnableConfig`용), `runtime`(`ToolRuntime`용)은 예약어. 도구 인자로 쓰면 런타임
오류. 런타임 정보는 `ToolRuntime` 파라미터로 접근한다.

## 컨텍스트 접근 (ToolRuntime)

도구 시그니처에 `runtime: ToolRuntime`를 추가하면 자동 주입되며, **LLM에게는 숨겨진다**(스키마에
나타나지 않음). 제공 항목 :

| 항목 | 설명 |
|---|---|
| State | 단기 메모리(메시지, 카운터, 커스텀 필드) |
| Context | 호출 시 전달되는 불변 설정(user ID, 세션 정보) |
| Store | 대화 간 유지되는 장기 메모리 |
| Stream Writer | 실행 중 실시간 업데이트 발행 |
| Execution Info | thread/run ID, 재시도 정보 |
| Server Info | LangGraph Server 메타데이터(assistant/graph ID, 인증 사용자) |
| Config | `RunnableConfig`(콜백/태그/메타데이터) |
| Tool Call ID | 현재 도구 호출의 고유 ID |

### State (단기 메모리)

```python
from langchain.tools import tool, ToolRuntime

@tool
def get_user_preference(pref_name: str, runtime: ToolRuntime) -> str:
    """Get a user preference value."""
    preferences = runtime.state.get("user_preferences", {})
    return preferences.get(pref_name, "Not set")
```

**State 업데이트** : `Command`로 상태를 갱신. 모델이 결과를 보도록 `ToolMessage`를 포함한다.

```python
from langgraph.types import Command
from langchain.messages import ToolMessage

@tool
def set_user_name(new_name: str, runtime: ToolRuntime[None, CustomState]) -> Command:
    """Set the user's name in the conversation state."""
    return Command(update={
        "user_name": new_name,
        "messages": [ToolMessage(content=f"User name set to {new_name}.",
                                 tool_call_id=runtime.tool_call_id)],
    })
```

LLM이 도구를 병렬 호출할 수 있으므로, 동일 필드 갱신 충돌 해결을 위해 reducer 정의를 고려한다.

### Context (불변 설정)

```python
from dataclasses import dataclass

@dataclass
class UserContext:
    user_id: str

@tool
def get_account_info(runtime: ToolRuntime[UserContext]) -> str:
    """Get the current user's account information."""
    user_id = runtime.context.user_id
    ...

agent = create_agent(model, tools=[get_account_info], context_schema=UserContext)
agent.invoke({"messages": [...]}, context=UserContext(user_id="user123"))
```

### Store (장기 메모리)

namespace/key 패턴. 운영에서는 `PostgresStore` 등 영속 구현 사용.

```python
@tool
def get_user_info(user_id: str, runtime: ToolRuntime) -> str:
    """Look up user info."""
    user_info = runtime.store.get(("users",), user_id)
    return str(user_info.value) if user_info else "Unknown user"

@tool
def save_user_info(user_id: str, user_info: dict, runtime: ToolRuntime) -> str:
    """Save user info."""
    runtime.store.put(("users",), user_id, user_info)
    return "Successfully saved user info."
```

### Stream Writer

```python
@tool
def get_weather(city: str, runtime: ToolRuntime) -> str:
    """Get weather for a given city."""
    writer = runtime.stream_writer
    writer(f"Looking up data for city: {city}")
    return f"It's always sunny in {city}!"
```

`runtime.stream_writer` 사용 시 도구는 LangGraph 실행 컨텍스트 내에서 호출되어야 한다.

### Execution Info / Server Info

`runtime.execution_info`(`thread_id`, `run_id`, `node_attempt`), `runtime.server_info`
(`assistant_id`, `graph_id`, `user.identity`; LangGraph Server 외부에선 `None`). 둘 다
`deepagents>=0.5.0`(또는 `langgraph>=1.1.5`) 필요.

## ToolNode

LangGraph 워크플로우에서 도구를 실행하는 프리빌트 노드. 병렬 실행/에러 처리/상태 주입을 자동
처리. `create_agent` 대신 세밀한 제어가 필요한 커스텀 워크플로우에 사용.

```python
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, MessagesState

tool_node = ToolNode([search, calculator])
builder = StateGraph(MessagesState)
builder.add_node("tools", tool_node)
```

### 도구 반환값

- **string** : 사람이 읽을 텍스트. `ToolMessage`로 변환됨. 상태 미변경.
- **object** (예: dict) : 구조화 데이터. 직렬화되어 도구 출력으로 전송. 상태 미변경.
- **Command** : 그래프 상태 갱신. `ToolMessage` 포함 가능(성공 확인용).

### 에러 처리

```python
ToolNode(tools)  # 기본: invocation 에러는 잡고 execution 에러는 재발생
ToolNode(tools, handle_tool_errors=True)  # 모든 에러 잡아 LLM에 메시지 반환
ToolNode(tools, handle_tool_errors="Something went wrong.")  # 커스텀 메시지
ToolNode(tools, handle_tool_errors=handle_error_fn)  # 커스텀 핸들러
ToolNode(tools, handle_tool_errors=(ValueError, TypeError))  # 특정 예외만
```

### tools_condition 라우팅

```python
from langgraph.prebuilt import ToolNode, tools_condition

builder.add_conditional_edges("llm", tools_condition)  # "tools" 또는 END로 라우팅
builder.add_edge("tools", "llm")
```

## 프리빌트 도구 / 서버 측 도구

LangChain은 웹 검색, 코드 인터프리터, DB 접근 등 다양한 프리빌트 도구/툴킷을 제공한다(integrations
페이지 참고). 일부 채팅 모델은 서버 측에서 실행되는 내장 도구(웹 검색, 코드 인터프리터)를 가진다.
