# 장기 메모리 (Long-term Memory)

원문 : https://docs.langchain.com/oss/python/langchain/long-term-memory

장기 메모리는 에이전트가 서로 다른 대화와 세션에 걸쳐 정보를 저장하고 회상하게 한다. 단일 스레드로 범위가 한정되는 단기 메모리와 달리, 장기 메모리는 스레드를 넘어 영속되며 언제든 회상 가능하다. 장기 메모리는 **LangGraph stores** 위에 구축되며, 데이터를 namespace와 key로 조직된 JSON 문서로 저장한다.

## 사용법

에이전트에 장기 메모리를 추가하려면 store를 만들어 `create_agent`에 전달한다.

### InMemoryStore

```python
from langchain.agents import create_agent
from langchain_core.runnables import Runnable
from langgraph.store.memory import InMemoryStore

# InMemoryStore는 인메모리 딕셔너리에 저장. 운영에서는 DB 기반 store 사용.
store = InMemoryStore()

agent: Runnable = create_agent("claude-sonnet-4-6", tools=[], store=store)
```

### PostgreSQL

```python
# pip install langgraph-checkpoint-postgres
from langchain.agents import create_agent
from langchain_core.runnables import Runnable
from langgraph.store.postgres import PostgresStore

DB_URI = "postgresql://postgres:postgres@localhost:5442/postgres?sslmode=disable"

with PostgresStore.from_conn_string(DB_URI) as store:
    store.setup()
    agent: Runnable = create_agent("claude-sonnet-4-6", tools=[], store=store)
```

도구는 `runtime.store` 매개변수로 store를 읽고 쓸 수 있다.

메모리 유형(semantic, episodic, procedural)과 메모리 작성 전략은 Memory 개념 가이드 참조.

## 메모리 저장 구조

LangGraph는 장기 메모리를 store에 JSON 문서로 저장한다. 각 메모리는 커스텀 `namespace`(폴더와 유사)와 고유 `key`(파일명과 유사)로 조직된다. namespace는 흔히 사용자/조직 ID나 정보 조직을 쉽게 하는 라벨을 포함한다. 이 구조가 메모리의 계층적 조직을 가능하게 하며, content 필터를 통한 교차 namespace 검색을 지원한다.

```python
from collections.abc import Sequence
from langgraph.store.base import IndexConfig
from langgraph.store.memory import InMemoryStore

def embed(texts: Sequence[str]) -> list[list[float]]:
    # 실제 임베딩 함수 또는 LangChain embeddings 객체로 교체
    return [[1.0, 2.0] for _ in texts]

store = InMemoryStore(index=IndexConfig(embed=embed, dims=2))
user_id = "my-user"
application_context = "chitchat"
namespace = (user_id, application_context)

store.put(namespace, "a-memory", {
    "rules": ["User likes short, direct language", "User only speaks English & python"],
    "my-key": "my-value",
})

# ID로 메모리 조회
item = store.get(namespace, "a-memory")

# namespace 내 메모리 검색 — content 동등성 필터, 벡터 유사도 정렬
items = store.search(namespace, filter={"my-key": "my-value"}, query="language preferences")
```

## 도구에서 장기 메모리 읽기

```python
from dataclasses import dataclass
from langchain.agents import create_agent
from langchain.tools import ToolRuntime, tool
from langchain_core.runnables import Runnable
from langgraph.store.memory import InMemoryStore

@dataclass
class Context:
    user_id: str

store = InMemoryStore()
store.put(("users",), "user_123", {"name": "John Smith", "language": "English"})

@tool
def get_user_info(runtime: ToolRuntime[Context]) -> str:
    """Look up user info."""
    assert runtime.store is not None
    user_id = runtime.context.user_id
    user_info = runtime.store.get(("users",), user_id)  # value와 metadata를 가진 StoreValue 반환
    return str(user_info.value) if user_info else "Unknown user"

agent: Runnable = create_agent(
    model="claude-sonnet-4-6",
    tools=[get_user_info],
    store=store,  # store를 에이전트에 전달 → 도구 실행 시 store 접근 가능
    context_schema=Context,
)

agent.invoke(
    {"messages": [{"role": "user", "content": "look up user information"}]},
    context=Context(user_id="user_123"),
)
```

## 도구에서 장기 메모리 쓰기

```python
from dataclasses import dataclass
from langchain.agents import create_agent
from langchain.tools import ToolRuntime, tool
from langchain_core.runnables import Runnable
from langgraph.store.memory import InMemoryStore
from typing_extensions import TypedDict

store = InMemoryStore()

@dataclass
class Context:
    user_id: str

class UserInfo(TypedDict):
    name: str

@tool
def save_user_info(user_info: UserInfo, runtime: ToolRuntime[Context]) -> str:
    """Save user info."""
    assert runtime.store is not None
    store = runtime.store
    user_id = runtime.context.user_id
    store.put(("users",), user_id, dict(user_info))  # (namespace, key, data)
    return "Successfully saved user info."

agent: Runnable = create_agent(
    model="claude-sonnet-4-6",
    tools=[save_user_info],
    store=store,
    context_schema=Context,
)

agent.invoke(
    {"messages": [{"role": "user", "content": "My name is John Smith"}]},
    context=Context(user_id="user_123"),
)

# store에 직접 접근해 값 조회
item = store.get(("users",), "user_123")
```

---

핵심 대비 : 단기 메모리(short-term-memory.md)는 checkpointer + thread_id로 단일 스레드 대화 이력을 다룬다. 장기 메모리는 store + namespace/key로 스레드·세션을 넘어 영속한다. PostgreSQL store는 `IndexConfig(embed=..., dims=...)`로 벡터 인덱스를 구성해 시맨틱 검색이 가능하다.
