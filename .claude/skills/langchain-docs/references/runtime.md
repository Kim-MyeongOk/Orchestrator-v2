# Runtime

원문 : https://docs.langchain.com/oss/python/langchain/runtime

`create_agent`는 내부적으로 LangGraph 런타임에서 실행된다. LangGraph는 다음 정보를 가진
`Runtime` 객체를 노출한다 :

1. **Context** : user id, DB 연결 등 호출별 정적 정보/의존성
2. **Store** : 장기 메모리용 `BaseStore` 인스턴스
3. **Stream writer** : `"custom"` 스트림 모드로 정보를 스트리밍하는 객체
4. **Execution info** : 현재 실행의 식별/재시도 정보(thread ID, run ID, attempt number)
5. **Server info** : LangGraph Server 실행 시 서버 메타데이터(assistant ID, graph ID, 인증 사용자)

런타임 컨텍스트는 도구/미들웨어에 **의존성 주입(DI)**을 제공한다. 값 하드코딩이나 전역 상태 대신
호출 시 런타임 의존성(DB 연결, user ID, 설정)을 주입해 테스트 용이성/재사용성/유연성을 높인다.

## 접근

`context_schema`로 `context` 구조를 정의하고, 호출 시 `context` 인자로 전달한다.

```python
from dataclasses import dataclass
from langchain.agents import create_agent

@dataclass
class Context:
    user_name: str

agent = create_agent(model="gpt-5-nano", tools=[...], context_schema=Context)
agent.invoke(
    {"messages": [{"role": "user", "content": "What's my name?"}]},
    context=Context(user_name="John Smith"),
)
```

## 도구 내부에서

`ToolRuntime` 파라미터로 접근. 컨텍스트 접근, 장기 메모리 읽기/쓰기, 커스텀 스트림 쓰기.

```python
from langchain.tools import tool, ToolRuntime

@tool
def fetch_user_email_preferences(runtime: ToolRuntime[Context]) -> str:
    """Fetch the user's email preferences from the store."""
    user_id = runtime.context.user_id
    preferences = "..."
    if runtime.store:
        if memory := runtime.store.get(("users",), user_id):
            preferences = memory.value["preferences"]
    return preferences
```

### Execution info / Server info (도구 내부)

```python
@tool
def context_aware_tool(runtime: ToolRuntime) -> str:
    """A tool that uses execution and server info."""
    info = runtime.execution_info
    print(f"Thread: {info.thread_id}, Run: {info.run_id}")
    server = runtime.server_info
    if server is not None:  # LangGraph Server 외부에선 None
        print(f"Assistant: {server.assistant_id}")
        if server.user is not None:
            print(f"User: {server.user.identity}")
    return "done"
```

`runtime.execution_info`/`runtime.server_info`는 `deepagents>=0.5.0`(또는 `langgraph>=1.1.5`) 필요.

## 미들웨어 내부에서

노드 스타일 훅은 `Runtime` 파라미터로, 랩 스타일 훅은 `ModelRequest.runtime`으로 접근. 동적
프롬프트 생성, 메시지 수정, 사용자 컨텍스트 기반 동작 제어에 사용.

```python
from langgraph.runtime import Runtime

@dynamic_prompt
def dynamic_system_prompt(request: ModelRequest) -> str:
    user_name = request.runtime.context.user_name
    return f"You are a helpful assistant. Address the user as {user_name}."

@before_model
def log_before_model(state: AgentState, runtime: Runtime[Context]) -> dict | None:
    print(f"Processing request for user: {runtime.context.user_name}")
    return None
```

### Execution/Server info (미들웨어 내부)

```python
@before_model
def auth_gate(state: AgentState, runtime: Runtime) -> dict | None:
    """Block unauthenticated users when running on LangGraph Server."""
    server = runtime.server_info
    if server is not None and server.user is None:
        raise ValueError("Authentication required")
    print(f"Thread: {runtime.execution_info.thread_id}")
    return None
```
