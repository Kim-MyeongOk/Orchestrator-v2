# Stores

원문 : https://docs.langchain.com/oss/python/langgraph/stores

스토어는 **스레드 간 장기 메모리**를 제공한다 (스레드별 checkpointer 영속성을 보완). 사용자 선호,
누적 지식, 단일 대화를 넘어 살아남아야 할 사실 등을 임의의 key-value로 저장한다.

> `InMemoryStore`는 개발/테스트용. 프로덕션은 `PostgresStore`/`MongoDBStore`/`RedisStore`.
> 모두 `BaseStore`를 상속 — 노드 시그니처의 타입 어노테이션으로 `BaseStore`를 쓴다.

## 기본 사용

```python
from langgraph.store.memory import InMemoryStore
store = InMemoryStore()

user_id = "1"
namespace_for_memory = (user_id, "memories")   # 네임스페이스는 임의 길이 튜플

memory_id = str(uuid.uuid4())
store.put(namespace_for_memory, memory_id, {"food_preference": "I like pizza"})

memories = store.search(namespace_for_memory)   # 리스트, 기본 limit=10
memories[-1].dict()
# {'value': {...}, 'key': '...', 'namespace': ['1', 'memories'], 'created_at': ..., 'updated_at': ...}
```

`Item` 속성 : `value`(dict), `key`, `namespace`(tuple, JSON 직렬화 시 list), `created_at`, `updated_at`.

## 네임스페이스 항목 나열

`query`/`filter` 없이 `search`하면 네임스페이스 prefix 아래 항목을 반환. 주의 :
- **prefix 매칭** : `("alice",)`는 `("alice", "memories")` 등 하위도 반환. 단일 레벨만 원하면 전체
  네임스페이스를 넘기거나 클라이언트에서 `item.namespace` 필터.
- **limit 초과는 조용히 잘림** — overflow 신호 없음. limit를 크게 잡거나 `offset` 페이지네이션.
- **기본 정렬은 백엔드별로 다름** : Postgres는 `updated_at` 내림차순, InMemory는 삽입 순서.
  순서가 중요하면 클라이언트에서 `item.updated_at` 정렬.

```python
# 페이지네이션
offset = 0
while True:
    page = store.search(("alice", "memories"), limit=50, offset=offset)
    if not page: break
    offset += 50

# 네임스페이스 탐색
namespaces = store.list_namespaces(prefix=("alice",), max_depth=2)
```

## 시맨틱 검색

임베딩 모델로 인덱스를 구성하면 의미 기반 검색 가능.

```python
from langchain.embeddings import init_embeddings

store = InMemoryStore(index={
    "embed": init_embeddings("openai:text-embedding-3-small"),
    "dims": 1536,
    "fields": ["food_preference", "$"],   # 임베딩할 필드 ($는 전체)
})

memories = store.search(namespace_for_memory, query="What does the user like to eat?", limit=3)
```

저장 시 임베딩 필드 제어 :
```python
store.put(ns, key, {"food_preference": "...", "context": "..."}, index=["food_preference"])  # 일부만 임베딩
store.put(ns, key, {"system_info": "..."}, index=False)   # 임베딩 안 함(검색은 불가, 조회는 가능)
```

## LangGraph에서 사용

checkpointer(스레드별 상태)와 store(스레드 간)를 함께 컴파일한다. 노드에서 `Runtime`으로 store 접근.

```python
from dataclasses import dataclass
from langgraph.runtime import Runtime
from langgraph.checkpoint.memory import InMemorySaver

@dataclass
class Context:
    user_id: str

graph = builder.compile(checkpointer=InMemorySaver(), store=store)

# 노드에서 메모리 쓰기
async def update_memory(state: MessagesState, runtime: Runtime[Context]):
    namespace = (runtime.context.user_id, "memories")
    await runtime.store.aput(namespace, str(uuid.uuid4()), {"memory": memory})

# 노드에서 메모리 읽기
async def call_model(state: MessagesState, runtime: Runtime[Context]):
    namespace = (runtime.context.user_id, "memories")
    memories = await runtime.store.asearch(namespace, query=state["messages"][-1].content, limit=3)
    info = "\n".join(d.value["memory"] for d in memories)

# 호출 시 thread_id + context(user_id)
graph.stream({"messages": [...]}, {"configurable": {"thread_id": "1"}},
             stream_mode="updates", context=Context(user_id="1"))
```

`user_id`가 같으면 다른 스레드에서도 같은 메모리에 접근한다.

LangSmith(Studio/호스티드)에서는 base store가 기본 제공된다. 시맨틱 검색은 `langgraph.json`의
`store.index` 설정이 필요하다 (`embed`, `dims`, `fields`).

## 커스텀 스토어 만들기

`BaseStore`를 상속해 5개 async 메서드 구현(sync는 선택이지만 권장).

| 메서드 | 설명 |
|---|---|
| `aput(namespace, key, value, index=None)` | 단일 항목 저장/덮어쓰기 |
| `aget(namespace, key)` | key로 단일 항목 조회 (없으면 `None`) |
| `adelete(namespace, key)` | 단일 항목 삭제 |
| `asearch(namespace_prefix, *, query=None, filter=None, limit=10, offset=0)` | prefix 검색(+시맨틱) |
| `alist_namespaces(*, prefix=None, suffix=None, max_depth=None, limit=100, offset=0)` | 네임스페이스 나열 |

정확한 시그니처는 `inspect.getsource(BaseStore)`로 확인.

**네임스페이스 설계** : prefix 매칭 + O(1) key 조회 지원. SQL 예 :
```sql
CREATE TABLE store_items (
    namespace   TEXT[] NOT NULL,
    key         TEXT NOT NULL,
    value       JSONB NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (namespace, key)
);
CREATE INDEX ON store_items USING gin(namespace);
```

**직렬화** : 값은 평범한 dict — 특수 serializer 불필요. `json.dumps`/JSONB 컬럼 사용.
**시맨틱 검색** : 벡터 검색 지원 시 `asearch`의 `query`를 구현(임베딩 후 코사인 유사도 랭킹, `score` 필드 포함).
미지원이면 `query` 전달 시 `NotImplementedError`. **테스트** : conformance suite 없음 — `InMemoryStore`를 레퍼런스로 비교 테스트.
