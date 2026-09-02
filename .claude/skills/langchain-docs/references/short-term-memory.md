# Short-term memory

원문 : https://docs.langchain.com/oss/python/langchain/short-term-memory

단기 메모리는 단일 스레드(대화) 내의 이전 상호작용을 기억하게 한다. 가장 흔한 형태는 대화
히스토리다. 긴 대화는 LLM 컨텍스트 윈도우를 초과해 컨텍스트 손실/오류를 유발하고, 컨텍스트가
길면 모델 성능이 떨어지고 응답이 느려지고 비용이 증가한다. (대화 **간** 기억은 long-term memory 참고)

## 사용법

에이전트 생성 시 `checkpointer`를 지정한다. 단기 메모리는 에이전트 상태(state)의 일부로 관리되며,
checkpointer를 통해 DB(또는 메모리)에 영속되어 언제든 스레드를 재개할 수 있다. 상태는 에이전트
호출 또는 단계(도구 호출 등) 완료 시 갱신되고, 각 단계 시작 시 읽힌다.

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

agent = create_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[get_user_info],
    checkpointer=InMemorySaver(),
)

thread_config = {"configurable": {"thread_id": "1"}}
agent.invoke({"messages": [{"role": "user", "content": "Hi! My name is Bob."}]}, thread_config)
agent.invoke({"messages": [{"role": "user", "content": "What's my name?"}]}, thread_config)
# "You are Bob!"
```

### 운영 환경

DB 기반 checkpointer를 사용한다.

```bash
pip install langgraph-checkpoint-postgres
```

```python
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = "postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable"
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()  # 테이블 자동 생성
    agent = create_agent("gpt-5.5", tools=[get_user_info], checkpointer=checkpointer)
```

SQLite, Postgres, Azure Cosmos DB 등 다양한 옵션 존재.

## 에이전트 메모리 커스터마이즈

기본적으로 `AgentState`로 단기 메모리(특히 `messages` 키의 대화 히스토리)를 관리한다. `AgentState`를
확장해 필드를 추가하고 `state_schema`로 전달한다.

```python
from langchain.agents import create_agent, AgentState

class CustomAgentState(AgentState):
    user_id: str
    preferences: dict

agent = create_agent("gpt-5.5", tools=[...], state_schema=CustomAgentState,
                     checkpointer=InMemorySaver())

agent.invoke(
    {"messages": [...], "user_id": "user_123", "preferences": {"theme": "dark"}},
    {"configurable": {"thread_id": "1"}})
```

## 공통 패턴 (컨텍스트 윈도우 관리)

### Trim messages (메시지 트리밍)

토큰 수를 세어 한도에 근접하면 잘라낸다. `@before_model` 미들웨어에서 처리.

```python
from langchain.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langchain.agents.middleware import before_model

@before_model
def trim_messages(state: AgentState, runtime) -> dict | None:
    messages = state["messages"]
    if len(messages) <= 3:
        return None
    first_msg = messages[0]
    recent = messages[-3:] if len(messages) % 2 == 0 else messages[-4:]
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), first_msg, *recent]}
```

### Delete messages (메시지 삭제)

`RemoveMessage`로 그래프 상태에서 영구 삭제. `add_messages` reducer를 쓰는 상태 키 필요(기본
`AgentState`가 제공).

```python
from langchain.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

# 특정 메시지 삭제
{"messages": [RemoveMessage(id=m.id) for m in messages[:2]]}
# 전체 삭제
{"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}
```

주의 : 삭제 후 메시지 히스토리가 유효해야 한다(일부 프로바이더는 `user` 메시지로 시작 요구, 도구
호출 `assistant` 메시지 뒤에 대응하는 `tool` 결과 필요).

### Summarize messages (요약)

트리밍/삭제는 정보 손실이 있으므로, 채팅 모델로 히스토리를 요약한다. 내장
`SummarizationMiddleware` 사용.

```python
from langchain.agents.middleware import SummarizationMiddleware

agent = create_agent(
    model="gpt-5.5", tools=[...],
    middleware=[SummarizationMiddleware(
        model="gpt-5.4-mini",
        trigger=("tokens", 4000),
        keep=("messages", 20),
    )],
    checkpointer=InMemorySaver(),
)
```

## 메모리 접근

### 도구에서

읽기 : `runtime.state[...]` (ToolRuntime, LLM에게 숨겨짐).
쓰기 : `Command(update={...})`를 반환해 상태 갱신(`ToolMessage` 포함).

```python
@tool
def get_user_info(runtime: ToolRuntime) -> str:
    """Look up user info."""
    user_id = runtime.state["user_id"]
    return "User is John Smith" if user_id == "user_123" else "Unknown user"
```

### 프롬프트에서

`@dynamic_prompt` 미들웨어로 상태/컨텍스트 기반 동적 프롬프트 생성.

```python
@dynamic_prompt
def dynamic_system_prompt(request: ModelRequest) -> str:
    user_name = request.runtime.context["user_name"]
    return f"You are a helpful assistant. Address the user as {user_name}."
```

### before_model / after_model 미들웨어에서

- `@before_model` : 모델 호출 **전** 메시지 처리(트리밍 등). 흐름 : start → before_model →
  model → (tools →) before_model → ... → end.
- `@after_model` : 모델 호출 **후** 메시지 처리(민감어 필터링 등). 흐름 : start → model →
  after_model → (tools → model →) ... → end.

```python
@after_model
def validate_response(state: AgentState, runtime) -> dict | None:
    """Remove messages containing sensitive words."""
    STOP_WORDS = ["password", "secret"]
    last_message = state["messages"][-1]
    if any(word in last_message.content for word in STOP_WORDS):
        return {"messages": [RemoveMessage(id=last_message.id)]}
    return None
```
