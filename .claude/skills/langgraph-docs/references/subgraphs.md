# Subgraphs

원문 : https://docs.langchain.com/oss/python/langgraph/use-subgraphs

서브그래프는 다른 그래프의 **노드로 사용되는 그래프**. 용도 : 멀티 에이전트 시스템, 노드 집합 재사용,
독립 개발(인터페이스만 지키면 부모는 내부를 몰라도 됨).

## 부모-서브그래프 통신 패턴

| 패턴 | 사용 시점 | 상태 스키마 |
|---|---|---|
| **노드 안에서 서브그래프 호출** | 부모·서브그래프 **상태 스키마가 다름**(공유 키 없음), 상태 변환 필요 | 부모 상태↔서브그래프 입출력을 매핑하는 래퍼 함수 작성 |
| **서브그래프를 노드로 추가** | 부모·서브그래프가 **상태 키 공유**(같은 채널 read/write) | 컴파일된 서브그래프를 `add_node`에 직접 전달, 래퍼 불필요 |

### 노드 안에서 호출 (다른 스키마)

```python
class SubgraphState(TypedDict):
    bar: str

subgraph = subgraph_builder.compile()

class State(TypedDict):
    foo: str

def call_subgraph(state: State):
    subgraph_output = subgraph.invoke({"bar": state["foo"]})   # 부모→서브그래프 변환
    return {"foo": subgraph_output["bar"]}                      # 서브그래프→부모 변환

builder.add_node("node_1", call_subgraph)
```

각 에이전트에 비공개 메시지 이력을 유지하려는 멀티 에이전트에서 흔하다. 다단계 중첩
(parent→child→grandchild)도 같은 방식으로 함수 안에서 호출하면 각 레벨의 키는 서로 접근 불가.

### 노드로 추가 (공유 스키마)

```python
class State(TypedDict):
    foo: str

subgraph = subgraph_builder.compile()

builder = StateGraph(State)
builder.add_node("node_1", subgraph)   # 컴파일된 서브그래프 직접 전달
```

서브그래프 노드는 자신만의 비공개 키(`bar`)를 쓰면서 공유 키(`foo`)에 업데이트를 보낼 수 있다.
멀티 에이전트에서 에이전트들이 공유 `messages` 키로 통신할 때 흔하다.

## 서브그래프 영속성 (`.compile(checkpointer=...)`)

호출 간 서브그래프 내부 데이터를 어떻게 할지 결정한다.

| 모드 | `checkpointer=` | 동작 |
|---|---|---|
| **Per-invocation** (기본) | `None` | 매 호출 새로 시작. 단일 호출 내에선 부모 checkpointer 상속(interrupt·durable execution 지원) |
| **Per-thread** | `True` | 같은 스레드에서 호출 간 상태 누적. 이전 호출 지점부터 이어감 |
| **Stateless** | `False` | 체크포인팅 없음. 평범한 함수 호출. interrupt·durable execution 불가 |

부모 그래프는 서브그래프 영속성 기능(interrupt, 상태 검사, per-thread 메모리)을 위해 checkpointer로
컴파일되어야 한다.

### Per-invocation (기본, 권장)

각 서브그래프 호출이 독립적이고 이전 호출을 기억할 필요 없을 때. 멀티 에이전트(서브에이전트를 도구로
호출)에 가장 흔함. interrupt·durable execution·병렬 호출 지원하면서 각 호출 격리. `checkpointer` 생략/None.

```python
# 서브에이전트 — checkpointer 미설정(부모 상속)
fruit_agent = create_agent(model="gpt-5.4-mini", tools=[fruit_info], prompt="...")

@tool
def ask_fruit_expert(question: str) -> str:
    """과일 전문가에게 묻습니다."""
    response = fruit_agent.invoke({"messages": [{"role": "user", "content": question}]})
    return response["messages"][-1].content

agent = create_agent(model="gpt-5.4-mini", tools=[ask_fruit_expert], checkpointer=MemorySaver())
```

각 호출은 새 서브에이전트 상태로 시작(이전 호출 기억 못함). 같은 서브그래프 다중 호출도 각자
체크포인트 네임스페이스를 받아 충돌 없음. 호출마다 `interrupt()`로 정지·재개 가능.

### Per-thread (`checkpointer=True`)

서브에이전트가 이전 상호작용을 기억해야 할 때(여러 교환에 걸쳐 컨텍스트를 쌓는 리서치 어시스턴트 등).
대화 이력이 같은 스레드의 호출 간 누적된다.

> **병렬 도구 호출 미지원** : LLM이 per-thread 서브에이전트 도구를 병렬 호출하면 같은 네임스페이스에
> 써서 체크포인트 충돌. LangChain `ToolCallLimitMiddleware(run_limit=1)`로 방지하거나, 순수
> LangGraph면 모델의 병렬 도구 호출을 비활성화한다.

**네임스페이스 격리** : 서로 다른 per-thread 서브그래프 여러 개는 각자 저장 공간이 필요하다.
노드 안에서 호출하면 호출 순서로 네임스페이스가 할당되어 재정렬 시 상태가 섞일 수 있다. 각 서브에이전트를
고유 노드명의 `StateGraph`로 감싸 안정적 네임스페이스 부여 :

```python
def create_sub_agent(model, *, name, **kwargs):
    agent = create_agent(model=model, name=name, **kwargs)
    return (StateGraph(MessagesState)
            .add_node(name, agent)     # 고유 이름 → 안정적 네임스페이스
            .add_edge("__start__", name)
            .compile())
```
(노드로 추가한 서브그래프는 이미 이름 기반 네임스페이스를 받으므로 이 래퍼 불필요.)

### Stateless (`checkpointer=False`)

평범한 함수 호출처럼 체크포인팅 오버헤드 없이 실행. pause/resume·durable execution 불가.
크래시 시 처음부터 재실행.

### 능력 비교표

| 기능 | Per-invocation | Per-thread | Stateless |
|---|---|---|---|
| `checkpointer=` | `None` | `True` | `False` |
| Interrupts (HITL) | ✅ | ✅ | ❌ |
| 멀티턴 메모리 | ❌ | ✅ | ❌ |
| 다중 호출(다른 서브그래프) | ✅ | ⚠️ | ✅ |
| 다중 호출(같은 서브그래프) | ✅ | ❌ | ✅ |
| 상태 검사 | ⚠️ | ✅ | ❌ |

## 서브그래프 상태 검사

```python
subgraph_state = graph.get_state(config, subgraphs=True).tasks[0].state
```

LangGraph가 서브그래프를 **정적으로 발견**할 수 있어야 한다(노드로 추가 또는 노드 안 호출). 도구
함수 안에서 호출하면(subagents 패턴) 동작 안 함. 단 interrupt는 중첩과 무관하게 최상위로 전파된다.
stateless(`checkpointer=False`)면 서브그래프 체크포인트가 없어 상태 조회 불가.

## 서브그래프 출력 스트리밍

부모 `.stream(..., subgraphs=True)`. v2에서 `ns` 필드가 소스 식별(`()`=루트, `("node_2:<task_id>",)`=서브그래프).

```python
for chunk in graph.stream({"foo": "foo"}, subgraphs=True, stream_mode="updates", version="v2"):
    if chunk["type"] == "updates":
        print(chunk["ns"], chunk["data"])
```
