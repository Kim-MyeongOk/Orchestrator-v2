# Graph API Overview

원문 : https://docs.langchain.com/oss/python/langgraph/graph-api

LangGraph는 에이전트 워크플로우를 그래프로 모델링한다. 세 컴포넌트 : **State**(현재 스냅샷 공유
데이터 구조), **Nodes**(로직을 인코딩한 함수, state 입력→계산→state 업데이트 반환), **Edges**(다음
실행 노드를 결정, 조건부 분기 또는 고정 전이). 요약 : *노드는 일하고, 엣지는 다음에 뭘 할지 알려준다.*

내부적으로 **message passing**으로 동작(Google Pregel 영감). 실행은 이산 **super-step**으로 진행 —
병렬 노드는 같은 super-step, 순차 노드는 별도 super-step. 모든 노드가 inactive이고 전송 중 메시지가
없으면 종료.

## StateGraph & 컴파일

`StateGraph`가 메인 클래스(사용자 정의 `State`로 파라미터화). state 정의 → 노드·엣지 추가 → 컴파일.
컴파일은 구조 검사(고아 노드 등)와 checkpointer·breakpoint 같은 런타임 인자 지정 지점. **사용 전 반드시 컴파일.**

```python
graph = graph_builder.compile(...)
```

## State

### 스키마

`TypedDict`(주 방법), 기본값 필요하면 `dataclass`, 재귀 검증 필요하면 Pydantic `BaseModel`(단 덜 성능적).
기본은 입출력 스키마가 같음. 명시적 input/output 스키마 분리 가능. (`create_agent` 팩토리는 Pydantic state 미지원.)

### 다중 스키마

노드가 비공개 채널로 내부 통신하거나, 입출력 스키마를 제약할 수 있다.

```python
class InputState(TypedDict):
    user_input: str
class OutputState(TypedDict):
    graph_output: str
class OverallState(TypedDict):
    foo: str
    user_input: str
    graph_output: str
class PrivateState(TypedDict):
    bar: str

builder = StateGraph(OverallState, input_schema=InputState, output_schema=OutputState)
```

핵심 : (1) 노드는 입력 스키마에 없어도 **그래프 상태의 어떤 채널에도 쓸 수 있다**(그래프 상태는 정의된
채널들의 합집합). (2) 스키마 정의가 존재하면 노드가 추가 채널(`PrivateState`의 `bar`)을 선언·기록 가능.

### Reducers

각 state 키는 독립 reducer를 가진다. 미지정 시 업데이트가 기존 값을 **덮어쓴다**(override).

```python
from operator import add
class State(TypedDict):
    foo: int
    bar: Annotated[list[str], add]   # add reducer → 리스트 연결
```
`{"bar": ["bye"]}` 업데이트 시 기본 reducer면 `["bye"]`로 교체, `add`면 `["hi", "bye"]`로 연결.

reducer를 우회해 직접 덮어쓰려면 `Overwrite` 타입 사용.

### 메시지 작업

대화 이력을 메시지 리스트로 저장. reducer가 핵심 — 미지정 시 매 업데이트가 리스트를 덮어씀. `operator.add`는
단순 추가지만 수동 업데이트(HITL) 시 기존 메시지 갱신 불가. prebuilt **`add_messages`**는 새 메시지는
추가하고 메시지 ID로 기존 메시지를 올바르게 갱신하며, dict↔LangChain Message 역직렬화도 처리.

```python
from langgraph.graph.message import add_messages
class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
```

`{"messages": [HumanMessage(content="msg")]}`와 `{"messages": [{"type": "human", "content": "msg"}]}` 둘 다 지원.
속성은 dot notation으로 접근 : `state["messages"][-1].content`.

**MessagesState** prebuilt — `messages` 키 하나에 `add_messages` reducer. 보통 서브클래싱해 필드 추가 :
```python
class State(MessagesState):
    documents: list[str]
```

## Nodes

동기/비동기 Python 함수. 인자 : `state`, `config`(RunnableConfig — thread_id·tags), `runtime`(Runtime —
`context`·`store`·`stream_writer`·`execution_info`·`server_info`·`heartbeat`·`control`).

```python
def node_with_runtime(state: State, runtime: Runtime[Context]):
    print(runtime.context.user_id)
    return {"results": f"Hello, {state['input']}!"}

builder.add_node("node_with_runtime", node_with_runtime)
builder.add_node(my_node)   # 이름 미지정 시 함수명이 기본 노드명
```

함수는 내부적으로 `RunnableLambda`로 변환(batch·async·추적 추가).

- **`START`** : 사용자 입력을 그래프로 보내는 특수 노드. `graph.add_edge(START, "node_a")`.
- **`END`** : 종료 노드. `graph.add_edge("node_a", END)`.

### 노드 캐싱

입력 기반 캐싱. 컴파일 시 cache 지정 + 노드에 `CachePolicy`(`key_func`, `ttl`).

```python
from langgraph.cache.memory import InMemoryCache
from langgraph.types import CachePolicy

builder.add_node("expensive_node", expensive_node, cache_policy=CachePolicy(ttl=3))
graph = builder.compile(cache=InMemoryCache())
# 두 번째 호출은 캐시 사용, __metadata__: {'cached': True}
```

## Edges

- **Normal** : 항상 A→B. `graph.add_edge("node_a", "node_b")`.
- **Conditional** : 라우팅 함수로 동적 결정. `graph.add_conditional_edges("node_a", routing_function)`,
  선택적 매핑 dict `{True: "node_b", False: "node_c"}`.
- **Entry point** : `add_edge(START, "node_a")`.
- **Conditional entry point** : `add_conditional_edges(START, routing_function)`.

노드가 여러 출력 엣지를 가지면 **모든** 목적지가 다음 super-step에서 병렬 실행.

> 노드마다 하나의 라우팅 메커니즘만 — 정적 라우팅은 normal edge, 동적은 conditional edge/`Command`.
> 같은 노드에서 normal edge와 동적 라우팅을 섞지 말 것(둘 다 실행되어 추론 어려움).

## Send (map-reduce)

사전에 엣지 수를 모르거나 다운스트림 노드에 객체별 다른 state를 넘길 때. 조건부 엣지에서 `Send` 객체
반환. `Send(노드명, state)`.

```python
from langgraph.types import Send

def continue_to_jokes(state: OverallState):
    return [Send("generate_joke", {"subject": s}) for s in state['subjects']]

graph.add_conditional_edges("node_a", continue_to_jokes)
```

## Command

그래프 실행을 제어하는 다목적 primitive. 4개 파라미터 : `update`(state 업데이트), `goto`(노드 이동),
`graph`(서브그래프→부모 타겟), `resume`(interrupt 후 재개 값).

### 노드에서 반환 (update + goto)

```python
def my_node(state: State) -> Command[Literal["my_other_node"]]:
    return Command(update={"foo": "bar"}, goto="my_other_node")
```

state 업데이트와 라우팅을 **둘 다** 할 때 사용(라우팅만이면 조건부 엣지). 반환 타입 어노테이션 필수
(`Command[Literal["my_other_node"]]`) — 그래프 렌더링·라우팅 정보. `Command`는 동적 엣지를 추가할 뿐
`add_edge` 정적 엣지는 여전히 실행(둘 다 라우팅하면 양쪽 실행).

### graph=Command.PARENT (서브그래프→부모)

```python
def my_node(state: State) -> Command[Literal["other_subgraph"]]:
    return Command(update={"foo": "bar"}, goto="other_subgraph", graph=Command.PARENT)
```
부모·서브그래프가 공유하는 키를 업데이트하면 부모 상태에 해당 키 **reducer 필수**. 멀티 에이전트 handoff에 유용.

### invoke/stream 입력 (resume만)

`Command(resume=...)`만 입력용. `Command(update=...)`를 멀티턴 대화 입력으로 쓰지 말 것 — 어떤
`Command`든 입력으로 넘기면 최신 체크포인트(마지막 실행 스텝, `__start__` 아님)에서 재개되어 이미
끝났으면 멈춘 것처럼 보임. 기존 스레드 대화 이어가기는 plain dict 사용.

```python
# 잘못 — 최신 체크포인트에서 재개, 멈춘 듯 보임
graph.invoke(Command(update={"messages": [...]}), config)
# 올바름 — __start__에서 재시작
graph.invoke({"messages": [...]}, config)
```

### resume

```python
from langgraph.types import Command, interrupt

def human_review(state: State):
    answer = interrupt("Do you approve?")   # 정지·값 대기
    return {"messages": [{"role": "user", "content": answer}]}

result = graph.invoke(Command(resume="yes"), config)   # interrupt()가 "yes" 반환
```

### 도구에서 반환

도구에서 `Command` 반환으로 state 업데이트·제어 흐름. `update`(대화 중 조회한 정보 저장), `goto`(도구 완료 후 노드 이동).

## Graph migrations

checkpointer 사용 시에도 마이그레이션 처리. 끝난(non-interrupted) 스레드는 전체 토폴로지 변경 가능.
interrupted 스레드는 노드 이름 변경/제거 외 모든 토폴로지 변경 지원. state 키 추가/제거는 완전 호환,
이름 변경은 기존 스레드의 저장 상태 손실.

## Runtime context

state가 아닌 정보(모델명, DB 연결 등)를 노드에 전달.

```python
@dataclass
class ContextSchema:
    llm_provider: str = "openai"

graph = StateGraph(State, context_schema=ContextSchema)
graph.invoke(inputs, context={"llm_provider": "anthropic"})

def node_a(state: State, runtime: Runtime[ContextSchema]):
    llm = get_llm(runtime.context.llm_provider)
```

## Recursion limit

단일 실행의 최대 super-step 수. 초과 시 `GraphRecursionError`. v1.0.6부터 기본 1000. `config`의
독립 키(`configurable` 안이 아님) :

```python
graph.invoke(inputs, config={"recursion_limit": 5})
```

현재 스텝은 `config["metadata"]["langgraph_step"]`. **`RemainingSteps`** managed value로 한계까지 남은
스텝 추적해 우아한 degradation :

```python
from langgraph.managed import RemainingSteps
class State(TypedDict):
    messages: Annotated[list, lambda x, y: x + y]
    remaining_steps: RemainingSteps   # 자동 채워짐

def route_decision(state: State):
    if state["remaining_steps"] <= 2:
        return "fallback_node"
    return "reasoning_node"
```

**Proactive(권장, 그래프 내 모니터링)** vs **Reactive(외부 try/except GraphRecursionError)** : proactive는
한계 전 감지·그래프 내 조건부 라우팅·중간 상태 체크포인트 저장·정상 완료. reactive는 단순하지만
그래프 종료됨.

기타 메타데이터 : `langgraph_node`, `langgraph_triggers`, `langgraph_path`, `langgraph_checkpoint_ns`.

## 시각화·추적

내장 시각화 방법 여러 개(use-graph-api 참조). 추적·디버그·평가는 LangSmith.
