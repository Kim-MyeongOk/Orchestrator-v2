# LangGraph Runtime (Pregel)

원문 : https://docs.langchain.com/oss/python/langgraph/pregel

`Pregel`이 LangGraph 런타임을 구현해 앱 실행을 관리한다. StateGraph 컴파일 또는 `@entrypoint` 생성은
`Pregel` 인스턴스를 만든다. (이름은 Google Pregel 알고리즘 — 그래프 기반 대규모 병렬 계산에서 유래.)

## 개요

Pregel은 **actor**와 **channel**을 결합. actor는 channel에서 읽고 channel에 쓴다. 실행은 **Bulk
Synchronous Parallel** 모델의 여러 스텝으로. 각 스텝의 3단계 :
- **Plan** : 이 스텝에 실행할 actor 결정(첫 스텝은 input 채널 구독 actor, 이후는 직전 스텝에서 갱신된 채널 구독 actor).
- **Execution** : 선택된 actor 병렬 실행(모두 완료/하나 실패/타임아웃까지). 채널 업데이트는 다음 스텝까지 actor에게 비가시.
- **Update** : actor가 쓴 값으로 채널 갱신.

실행할 actor가 없거나 최대 스텝 도달까지 반복.

## Actors

**actor** = `PregelNode`. 채널 구독·읽기·쓰기. LangChain Runnable 인터페이스 구현.

## Channels

actor 간 통신. 각 채널은 값 타입·업데이트 타입·업데이트 함수(업데이트 시퀀스→저장값 수정)를 가진다.

### LastValue (기본)
마지막 쓴 값 저장(이전 값 덮어씀). 입출력 값, 스텝 간 데이터 전달.
```python
from langgraph.channels import LastValue
channel: LastValue[int] = LastValue(int)
```

### Topic
설정 가능한 PubSub 채널. 여러 값 전송 또는 스텝 간 출력 누적. 중복 제거 또는 전체 누적 설정.
```python
from langgraph.channels import Topic
channel: Topic[str] = Topic(str, accumulate=True)
```

### BinaryOperatorAggregate
현재 값과 새 업데이트에 이항 연산자 적용해 영속 값 갱신(running aggregate).
```python
import operator
from langgraph.channels import BinaryOperatorAggregate
total = BinaryOperatorAggregate(int, operator.add)
```

### DeltaChannel (beta, langgraph>=1.2)

매 스텝 전체 누적값 대신 **증분 델타만 저장**. 자주 쓰이고 시간이 지나며 큰 값을 누적하는 채널(장시간
스레드의 대화 메시지 리스트 등)에 유용. 델타 저장 없으면 전체 리스트가 매 체크포인트에 재직렬화되지만,
`DeltaChannel`은 매 스텝 새 메시지만 저장.

> 신호 : 특정 채널의 체크포인트 크기가 스레드 길이에 선형 증가하면 `DeltaChannel` 적합.
> (icodebroker의 PostgreSQL 콜드 스토리지 + AIMessageChunk 누적 인프라와 관련성 높음.)

```python
from langgraph.channels import DeltaChannel

def my_reducer(state: list[str], writes: Sequence[list[str]]) -> list[str]:
    result = list(state)
    for write in writes:
        result.extend(write)
    return result

class State(TypedDict):
    messages: Annotated[list[str], DeltaChannel(my_reducer)]
```

**Bulk reducer 요구** : `DeltaChannel`의 reducer는 **bulk reducer** — 현재 상태와 현재 스텝의 **모든 쓰기
시퀀스**를 한 번에 받음(StateGraph의 per-key reducer처럼 pairwise 아님). 반드시 **결합법칙(associative)** 만족 :
```
reducer(reducer(state, [xs]), [ys]) == reducer(state, [xs, ys])
```
비결합적이면 LangGraph의 쓰기 배칭 방식에 따라 재구성 상태가 달라져 비일관 동작. 흔한 bulk reducer :
list는 순서대로 extend, dict는 merge(키 충돌 시 마지막 우선).

**snapshot_frequency** : 스냅샷 없으면 `DeltaChannel` 읽기가 전체 쓰기 이력 재생 필요(N 스텝에 O(N)).
`snapshot_frequency=K`는 K 스텝마다 전체 스냅샷 기록해 읽기 깊이를 최대 K로 제한.
```python
messages: Annotated[list[str], DeltaChannel(my_reducer, snapshot_frequency=5)]
```
높은 값=저장 오버헤드↓ 읽기 지연↑, 낮은 값=지연 제한↑ 체크포인트↑. `None`(기본)은 스냅샷 생략(읽기 드물거나 짧은 스레드에 적합).

## 저수준 Pregel API (직접 사용)

대부분 StateGraph/`@entrypoint`로 상호작용하지만 Pregel 직접 사용 가능.

```python
from langgraph.channels import EphemeralValue
from langgraph.pregel import Pregel, NodeBuilder

node1 = NodeBuilder().subscribe_only("a").do(lambda x: x + x).write_to("b")

app = Pregel(
    nodes={"node1": node1},
    channels={"a": EphemeralValue(str), "b": EphemeralValue(str)},
    input_channels=["a"],
    output_channels=["b"],
)
app.invoke({"a": "foo"})   # {'b': 'foofoo'}
```

사이클 : 구독하는 채널에 쓰면 됨. `None` 쓸 때까지 계속(`ChannelWriteEntry("value", skip_none=True)`).

## 고수준 API

StateGraph(Graph API)와 Functional API 모두 컴파일/`@entrypoint` 시 Pregel 앱을 자동 생성. 컴파일된
인스턴스의 `graph.nodes`·`graph.channels`로 노드·채널 검사 가능.
