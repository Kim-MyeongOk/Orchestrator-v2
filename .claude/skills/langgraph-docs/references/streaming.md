# Streaming (stream-mode API)

원문 : https://docs.langchain.com/oss/python/langgraph/streaming

> 신규 앱은 **event streaming**(v1.2의 타입드 프로젝션 API, `event-streaming.md`)을 권장한다.
> 이 페이지는 stream-mode API(`updates`/`values`/`messages`/`custom`/`checkpoints`/`tasks`/`debug`)를 다룬다.

## 기본 사용

`graph.stream`(sync) / `graph.astream`(async)이 스트림 출력을 이터레이터로 yield한다.

```python
for chunk in graph.stream(
    {"topic": "ice cream"},
    stream_mode=["updates", "custom"],
    version="v2",
):
    if chunk["type"] == "updates":
        for node_name, state in chunk["data"].items():
            print(f"Node {node_name} updated: {state}")
    elif chunk["type"] == "custom":
        print(f"Status: {chunk['data']['status']}")
```

## v2 출력 포맷 (LangGraph >= 1.1 권장)

`version="v2"`를 전달하면 모드/개수/서브그래프와 무관하게 모든 청크가 통일된 `StreamPart` dict :

```python
{
    "type": "values" | "updates" | "messages" | "custom" | "checkpoints" | "tasks" | "debug",
    "ns": (),       # 네임스페이스 튜플 (서브그래프 이벤트에 채워짐)
    "data": ...,    # 모드별 페이로드
}
```

모드별 `TypedDict`(`ValuesStreamPart` 등)는 `langgraph.types`에서 임포트. `chunk["type"]`로 타입 내로잉.
v1(기본)은 모드/서브그래프에 따라 포맷이 달라진다(단일=raw, 다중=`(mode, data)`, 서브그래프=`(namespace, data)`).

## Stream modes

| 모드 | 설명 |
|---|---|
| `values` | 매 스텝 후 **전체 상태** |
| `updates` | 매 스텝 후 **상태 업데이트**(노드명+변경분). 같은 스텝 다중 업데이트는 개별 스트리밍 |
| `messages` | LLM 호출의 `(message_chunk, metadata)` 2-튜플 (토큰 단위) |
| `custom` | 노드/도구에서 `get_stream_writer`로 emit한 커스텀 데이터 |
| `checkpoints` | 체크포인트 이벤트(`get_state()`와 동일 포맷). **checkpointer 필요** |
| `tasks` | task 시작/완료 이벤트(결과·에러). **checkpointer 필요** |
| `debug` | 가능한 모든 정보. `checkpoints`+`tasks`+추가 메타데이터 |

## LLM 토큰 (`messages` 모드)

그래프 어디서든(노드/도구/서브그래프/태스크) LLM 출력을 **토큰 단위**로 스트리밍.
`.invoke`로 LLM을 실행해도 message 이벤트는 emit된다.

```python
for chunk in graph.stream({"topic": "ice cream"}, stream_mode="messages", version="v2"):
    if chunk["type"] == "messages":
        message_chunk, metadata = chunk["data"]
        if message_chunk.content:
            print(message_chunk.content, end="|", flush=True)
```

**LLM 호출별 필터** : 모델에 `tags=['joke']`를 달고 `metadata["tags"]`로 필터.
**노드별 필터** : `metadata["langgraph_node"]`로 필터.
**스트림 제외** : `nostream` 태그 모델의 토큰은 `messages` 모드에서 제외(실행·출력은 됨). 내부 처리용
구조화 출력이나 중복 방지에 유용.

```python
model = init_chat_model(...).with_config({"tags": ["nostream"]})
```

## Custom 데이터 (`custom` 모드)

노드/도구 안에서 `get_stream_writer`로 사용자 정의 데이터를 emit. `stream_mode`에 `"custom"` 포함 필요.

```python
from langgraph.config import get_stream_writer

def node(state):
    writer = get_stream_writer()
    writer({"custom_key": "진행 상황"})
    return {"answer": "some data"}

@tool
def query_database(query: str) -> str:
    """데이터베이스를 조회합니다."""
    writer = get_stream_writer()
    writer({"data": "Retrieved 0/100 records", "type": "progress"})
    ...
    writer({"data": "Retrieved 100/100 records", "type": "progress"})
    return "some-answer"
```

## 서브그래프 출력

부모 `.stream(..., subgraphs=True)`로 부모+서브그래프 출력을 함께 스트리밍. v2에서는 `ns` 필드가
소스를 식별(`()`=루트, `("node_name:<task_id>",)`=서브그래프).

```python
for chunk in graph.stream({"foo": "foo"}, subgraphs=True, stream_mode="updates", version="v2"):
    if chunk["ns"]:
        print(f"Subgraph {chunk['ns']}: {chunk['data']}")
    else:
        print(f"Root: {chunk['data']}")
```

## 임의의 LLM과 함께 (`custom` 모드)

LangChain 채팅 모델 인터페이스를 구현하지 않은 **어떤 LLM API든** `custom` 모드로 스트리밍.
raw 클라이언트나 외부 서비스의 자체 스트리밍을 통합할 때 사용.

```python
def call_arbitrary_model(state):
    writer = get_stream_writer()
    for chunk in your_custom_streaming_client(state["topic"]):
        writer({"custom_llm_chunk": chunk})
    return {"result": "completed"}
```

## 특정 모델 스트리밍 비활성화

```python
model = init_chat_model("claude-sonnet-4-6", streaming=False)
# streaming 미지원 모델은 disable_streaming=True (모든 채팅 모델 base 클래스 제공)
```

## v2 invoke 포맷

`invoke(..., version="v2")`는 `.value`와 `.interrupts` 속성을 가진 `GraphOutput` 반환.

```python
from langgraph.types import GraphOutput
result = graph.invoke(inputs, version="v2")
result.value       # dict / Pydantic 모델 / dataclass
result.interrupts  # tuple[Interrupt, ...]

if result.interrupts:
    print(result.interrupts[0].value)
    graph.invoke(Command(resume=True), config=config, version="v2")
```

(dict 스타일 접근 `result["__interrupt__"]`은 deprecated.) Pydantic/dataclass 상태는 v2 `values`
모드에서 자동으로 해당 타입으로 coerce된다.

## Python < 3.11 비동기 주의

asyncio task가 `context`를 지원하지 않아 :
1. async LLM 호출(`ainvoke()`)에 **`RunnableConfig`를 명시적으로 전달**해야 콜백이 전파됨.
2. async 노드/도구에서 `get_stream_writer` 사용 불가 → `writer` 인자를 직접 받는다.

```python
from langgraph.types import StreamWriter

async def generate_joke(state, writer: StreamWriter):   # writer 인자 직접 주입
    writer({"custom_key": "..."})
    return {"joke": "..."}

async def call_model(state, config):                     # config 명시 전달
    joke_response = await model.ainvoke([...], config)
    return {"joke": joke_response.content}
```
