# Memory (add-memory)

원문 : https://docs.langchain.com/oss/python/langgraph/add-memory

두 종류의 메모리 :
- **단기 메모리** (스레드 레벨 영속) : 멀티턴 대화. checkpointer로 추가.
- **장기 메모리** (세션 간) : 사용자/앱 데이터. store로 추가.

## 단기 메모리 (checkpointer)

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
graph.invoke({"messages": [{"role": "user", "content": "hi! i am Bob"}]},
             {"configurable": {"thread_id": "1"}})
```

**프로덕션** : DB 백엔드 checkpointer. 첫 사용 시 `setup()` 호출 필요.

```python
# PostgreSQL
from langgraph.checkpoint.postgres import PostgresSaver
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    # checkpointer.setup()
    graph = builder.compile(checkpointer=checkpointer)

# Redis (async)
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
async with AsyncRedisSaver.from_conn_string("redis://localhost:6379") as checkpointer:
    # await checkpointer.asetup()
    graph = builder.compile(checkpointer=checkpointer)
```

지원 백엔드 : Postgres(`langgraph-checkpoint-postgres`), Redis(`langgraph-checkpoint-redis`),
MongoDB(`langgraph-checkpoint-mongodb`), Oracle(`langgraph-oracledb`), SQLite. 각 sync/async 버전 존재.

**서브그래프** : 부모 그래프 컴파일 시에만 checkpointer를 제공하면 자식 서브그래프에 자동 전파.
서브그래프별 동작 제어는 `subgraph.compile(checkpointer=True)`. 자세히는 `subgraphs.md`.

## 장기 메모리 (store)

```python
from langgraph.store.memory import InMemoryStore
store = InMemoryStore()
graph = builder.compile(store=store)
```

**노드에서 store 접근** : `Runtime` 객체로 자동 주입.

```python
from dataclasses import dataclass
from langgraph.runtime import Runtime
import uuid

@dataclass
class Context:
    user_id: str

async def call_model(state: MessagesState, runtime: Runtime[Context]):
    user_id = runtime.context.user_id
    namespace = (user_id, "memories")
    memories = await runtime.store.asearch(namespace, query=state["messages"][-1].content, limit=3)
    info = "\n".join(d.value["data"] for d in memories)
    # ... 모델 호출에 메모리 사용
    await runtime.store.aput(namespace, str(uuid.uuid4()), {"data": "User prefers dark mode"})

builder = StateGraph(MessagesState, context_schema=Context)
graph = builder.compile(store=store)

graph.invoke({"messages": [...]}, {"configurable": {"thread_id": "1"}}, context=Context(user_id="1"))
```

**프로덕션** : `PostgresStore`/`RedisStore`/`OracleStore` 등. checkpointer와 함께 컴파일 :
```python
with (PostgresStore.from_conn_string(DB_URI) as store,
      PostgresSaver.from_conn_string(DB_URI) as checkpointer):
    graph = builder.compile(checkpointer=checkpointer, store=store)
```

**시맨틱 검색** : 임베딩 모델로 인덱스 구성.
```python
from langchain.embeddings import init_embeddings
store = InMemoryStore(index={"embed": init_embeddings("openai:text-embedding-3-small"), "dims": 1536})
store.put(("user_123", "memories"), "1", {"text": "I love pizza"})
items = store.search(("user_123", "memories"), query="I'm hungry", limit=1)
```

## 단기 메모리 관리 (긴 대화)

긴 대화가 컨텍스트 윈도를 초과할 때 :

**메시지 트리밍** (`trim_messages`) :
```python
from langchain_core.messages.utils import trim_messages, count_tokens_approximately

def call_model(state: MessagesState):
    messages = trim_messages(state["messages"], strategy="last",
                             token_counter=count_tokens_approximately, max_tokens=128,
                             start_on="human", end_on=("human", "tool"))
    return {"messages": [model.invoke(messages)]}
```

**메시지 삭제** (`RemoveMessage`, `add_messages` reducer 필요) :
```python
from langchain.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

def delete_messages(state):
    messages = state["messages"]
    if len(messages) > 2:
        return {"messages": [RemoveMessage(id=m.id) for m in messages[:2]]}  # 특정 삭제
    # 전체 삭제 : return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}
```
> 주의 : 삭제 후 메시지 이력이 유효해야 함(프로바이더가 user 메시지로 시작 요구, tool_calls 뒤
> 대응 tool 결과 요구 등).

**요약** (`summarize`) : 이전 메시지를 요약으로 대체. `MessagesState`에 `summary` 키 확장.
```python
def summarize_conversation(state: State):
    summary = state.get("summary", "")
    summary_message = (f"This is a summary ...: {summary}\n\nExtend ..." if summary
                       else "Create a summary of the conversation above:")
    messages = state["messages"] + [HumanMessage(content=summary_message)]
    response = model.invoke(messages)
    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]  # 최근 2개만 유지
    return {"summary": response.content, "messages": delete_messages}
```
(langmem의 `SummarizationNode`/`RunningSummary`로 자동화 가능.)

## 체크포인트 관리

```python
config = {"configurable": {"thread_id": "1"}}   # checkpoint_id 추가 가능
graph.get_state(config)                          # 스레드 상태 (또는 checkpointer.get_tuple(config))
list(graph.get_state_history(config))            # 이력 (또는 checkpointer.list(config))
checkpointer.delete_thread("1")                  # 스레드의 모든 체크포인트 삭제
```

## DB 마이그레이션

DB 백엔드 영속성은 스키마 셋업을 위해 마이그레이션 필요. 대부분 `setup()` 메서드 제공(정확한
이름은 구현 확인). 전용 배포 스텝이나 서버 시작 시 실행 권장.
