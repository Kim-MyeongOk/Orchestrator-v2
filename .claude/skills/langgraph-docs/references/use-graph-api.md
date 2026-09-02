# Use the Graph API (실전 가이드)

원문 : https://docs.langchain.com/oss/python/langgraph/use-graph-api

graph-api.md의 개념을 실제 코드로 다루는 how-to. state, 시퀀스·분기·루프, Send(map-reduce), Command 등.

## state 정의·업데이트

state는 `TypedDict`/Pydantic/dataclass. 노드는 state를 **변경(mutate)하지 말고** 업데이트를 반환.

```python
class State(TypedDict):
    messages: list[AnyMessage]
    extra_field: int

def node(state: State):
    new_message = AIMessage("Hello!")
    return {"messages": [new_message], "extra_field": 10}   # 업데이트만 반환

builder = StateGraph(State)
builder.add_node(node)
builder.set_entry_point("node")
graph = builder.compile()
result = graph.invoke({"messages": [HumanMessage("Hi")]})   # 전체 state 반환
```

### reducer

```python
from operator import add
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add]   # 자동 추가(연결)
```

### add_messages / MessagesState

`add_messages`는 새 메시지 추가 + ID로 기존 메시지 갱신 + dict↔Message 역직렬화 처리.

```python
from langgraph.graph import MessagesState
class State(MessagesState):   # messages 키 + add_messages 내장
    extra_field: int
```

### Overwrite (reducer 우회)

```python
from langgraph.types import Overwrite
def replace_messages(state: State):
    return {"messages": Overwrite(["replacement"])}   # reducer 우회, 채널 직접 설정
    # 또는 {"messages": {"__overwrite__": ["replacement"]}}
```
병렬 super-step에서 같은 키에 한 노드만 Overwrite 가능(여럿이면 `InvalidUpdateError`).

### 입출력 스키마 분리

```python
class InputState(TypedDict):
    question: str
class OutputState(TypedDict):
    answer: str
class OverallState(InputState, OutputState):
    pass

builder = StateGraph(OverallState, input_schema=InputState, output_schema=OutputState)
# invoke 결과는 output 스키마만 포함
```

### 노드 간 private state

`add_sequence`로 연결 시, 노드 입력 타입 어노테이션으로 private 데이터를 특정 노드끼리만 전달.
한 노드가 `Node1Output`(private) 반환 → 다음 노드가 `Node2Input`(그 private 요청), 세 번째는 public만 접근.

### Pydantic state

입력 **런타임 검증** 추가. 제약 : 출력은 Pydantic 인스턴스 아님, 검증은 첫 노드 입력만, 재귀 검증 느림.
메시지는 `AnyMessage`(BaseMessage 아님) 사용해 올바른 직렬화.

## 런타임 설정 (context)

state를 오염시키지 않고 런타임에 LLM·시스템 프롬프트 등 지정.

```python
@dataclass
class ContextSchema:
    model_provider: str = "anthropic"

def call_model(state: MessagesState, runtime: Runtime[ContextSchema]):
    model = MODELS[runtime.context.model_provider]
    return {"messages": [model.invoke(state["messages"])]}

builder = StateGraph(MessagesState, context_schema=ContextSchema)
graph.invoke({"messages": [...]}, context={"model_provider": "openai"})
```

## retry 정책

```python
from langgraph.types import RetryPolicy
builder.add_node("query_database", query_database,
                 retry_policy=RetryPolicy(retry_on=sqlite3.OperationalError))
builder.add_node("model", call_model, retry_policy=RetryPolicy(max_attempts=5))
```
기본 `retry_on`은 `ValueError`/`TypeError`/`RuntimeError`/`OSError` 등 제외 모든 예외 재시도. requests/httpx는 5xx만.

## 노드에서 실행 정보 접근

`runtime.execution_info` : `thread_id`, `run_id`, `checkpoint_id`/`checkpoint_ns`, `task_id`,
`node_attempt`(1-indexed, 첫 시도 1, 첫 재시도 2), `node_first_attempt_time`.

```python
def my_node(state: State, runtime: Runtime):
    info = runtime.execution_info
    if info.node_attempt > 1:
        return {"result": call_fallback_api()}   # 재시도 시 fallback
    return {"result": call_primary_api()}
```

`runtime.server_info`(LangGraph Server에서만, 아니면 None) : `assistant_id`, `graph_id`, `user`.
> `execution_info`/`server_info`는 `deepagents>=0.5.0`(또는 `langgraph>=1.1.5`) 필요.

## 노드 캐싱

```python
from langgraph.types import CachePolicy
from langgraph.cache.memory import InMemoryCache   # 또는 SqliteCache

builder.add_node("node_name", node_function, cache_policy=CachePolicy(ttl=120))
graph = builder.compile(cache=InMemoryCache())
```

## 시퀀스

```python
builder = StateGraph(State).add_sequence([step_1, step_2, step_3])   # 단축
builder.add_edge(START, "step_1")
```

## 분기 (병렬)

fan-out/fan-in. reducer로 병렬 결과 누적.

```python
class State(TypedDict):
    aggregate: Annotated[list, operator.add]

builder.add_edge(START, "a")
builder.add_edge("a", "b")    # a → b, c 병렬
builder.add_edge("a", "c")
builder.add_edge("b", "d")    # b, c → d (둘 다 끝나야 d)
builder.add_edge("c", "d")
```

병렬 super-step 업데이트는 순서 일정치 않을 수 있음 → 순서 필요하면 별도 필드에 정렬값과 함께 기록.
super-step은 **트랜잭션** — 한 브랜치 예외 시 전체 업데이트 미적용(단 checkpointer 시 성공 노드 결과는 저장,
재개 시 반복 안 함). 실패 브랜치만 retry. `max_concurrency`로 동시성 제어.

### defer (지연 실행)

브랜치 길이가 다를 때 모든 pending 작업 완료까지 노드 지연.
```python
builder.add_node(d, defer=True)   # 모든 브랜치 완료 후 d 실행
```

### 조건부 분기

```python
def conditional_edge(state: State) -> Literal["b", "c"]:
    return state["which"]
builder.add_conditional_edges("a", conditional_edge)

# 여러 목적지로도 라우팅
def route_bc_or_cd(state) -> Sequence[str]:
    return ["c", "d"] if state["which"] == "cd" else ["b", "c"]
```

## Map-Reduce (Send API)

```python
from langgraph.types import Send

def continue_to_jokes(state: OverallState):
    return [Send("generate_joke", {"subject": s}) for s in state["subjects"]]

builder.add_conditional_edges("generate_topics", continue_to_jokes, ["generate_joke"])
```

## 루프

종료 조건을 위한 조건부 엣지 필요.

```python
def route(state: State) -> Literal["b", END]:
    if len(state["aggregate"]) < 7:
        return "b"
    return END

builder.add_edge(START, "a")
builder.add_conditional_edges("a", route)
builder.add_edge("b", "a")
```

재귀 한계 : `{"recursion_limit": N}` → `GraphRecursionError`. `RemainingSteps`로 에러 대신 마지막 상태 반환 :
```python
from langgraph.managed.is_last_step import RemainingSteps
class State(TypedDict):
    aggregate: Annotated[list, operator.add]
    remaining_steps: RemainingSteps

def route(state: State) -> Literal["b", END]:
    return END if state["remaining_steps"] <= 2 else "b"
```

## Async

노드를 `async def`로, 내부에 `await`, `.ainvoke`/`.astream`으로 호출.
```python
async def node(state: MessagesState):
    new_message = await llm.ainvoke(state["messages"])
    return {"messages": [new_message]}
result = await graph.ainvoke({"messages": [...]})
```

## Command (제어 흐름 + state 업데이트)

```python
def node_a(state: State) -> Command[Literal["node_b", "node_c"]]:
    value = random.choice(["b", "c"])
    goto = "node_b" if value == "b" else "node_c"
    return Command(update={"foo": value}, goto=goto)   # 업데이트 + 라우팅 동시
# 이 경우 그래프에 조건부 엣지 불필요(Command가 제어 흐름 정의)
```
반환 타입 어노테이션(`Command[Literal[...]]`) 필수.

### 부모 그래프로 이동 (Command.PARENT)

```python
return Command(update={"foo": value}, goto="node_b", graph=Command.PARENT)
```
부모·서브그래프 공유 키 업데이트 시 부모 상태에 **reducer 필수**.

### 도구 안에서 state 업데이트

```python
from langchain.tools import ToolRuntime

@tool
def lookup_user_info(runtime: ToolRuntime):
    """사용자 정보를 조회합니다."""
    user_info = get_user_info(runtime.server_info.user.identity)
    return Command(update={
        "user_info": user_info,
        "messages": [ToolMessage("Successfully looked up", tool_call_id=runtime.tool_call_id)],
    })
```
도구에서 `Command` 반환 시 `messages`에 **`ToolMessage` 필수 포함**(AI 메시지의 tool call은 tool 결과가
뒤따라야 유효). prebuilt `ToolNode`가 도구의 Command 반환을 자동 처리·전파.

## 시각화

```python
print(app.get_graph().draw_mermaid())           # Mermaid 구문
display(Image(app.get_graph().draw_mermaid_png()))  # PNG (Mermaid.Ink API 기본)
# Pyppeteer(pip install pyppeteer) 또는 graphviz(draw_png()) 옵션
```
