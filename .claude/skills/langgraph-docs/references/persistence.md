# Persistence

원문 : https://docs.langchain.com/oss/python/langgraph/persistence

LangGraph는 그래프 상태를 **체크포인트(checkpoint)**로 저장하는 내장 영속성 계층을 가진다.
checkpointer로 컴파일하면 실행의 매 스텝마다 상태 스냅샷이 **스레드(thread)** 단위로 저장된다.
이것이 HITL, 대화 메모리, time travel 디버깅, fault-tolerant 실행을 가능하게 한다.

> Agent Server(LangSmith) 사용 시 checkpointer를 수동 구성할 필요 없다 — 서버가 자동 처리.

## 영속성이 필요한 기능

- **Human-in-the-loop** : 상태 검사·중단·승인. 그래프가 사람 수정 후 재개해야 하므로 필수.
- **Memory** : 반복 상호작용(대화) 간 메모리 유지. 후속 메시지를 같은 스레드로 보낸다.
- **Time travel** : 과거 실행 재생/디버그, 임의 체크포인트에서 fork.
- **Fault-tolerance** : 노드 실패 시 마지막 성공 스텝부터 재시작.
- **Pending writes** : 한 super-step에서 노드가 중간 실패해도, 같은 step의 성공한 노드 쓰기는
  저장되어 재개 시 재실행하지 않는다.

## 핵심 개념

### Threads (스레드)
checkpointer가 저장하는 각 체크포인트에 부여되는 고유 ID. run 시퀀스의 누적 상태를 담는다.
checkpointer로 그래프 호출 시 `thread_id`를 **반드시** 지정한다.

```python
{"configurable": {"thread_id": "1"}}
```

`thread_id`는 체크포인트 저장/조회의 primary key다. 없으면 interrupt 후 재개 불가.

### Checkpoints (체크포인트)
특정 시점 스레드 상태의 스냅샷. `StateSnapshot` 객체로 표현. 각 **super-step** 경계에서 생성.

**Super-step** : 그래프의 한 "틱". 해당 스텝에 스케줄된 모든 노드가 (병렬로) 실행된다.
`START -> A -> B -> END`이면 입력·노드A·노드B 각각에 super-step이 있어 각각 후 체크포인트 생성.
time travel은 super-step 경계(체크포인트)에서만 재개 가능.

노드(task) 레벨 쓰기도 별도로 영속화되어 pending writes 복구를 가능하게 한다.

### Checkpoint namespace (`checkpoint_ns`)
- `""` : 부모(루트) 그래프
- `"node_name:uuid"` : 해당 노드로 호출된 서브그래프. 중첩 시 `|`로 연결.

```python
def my_node(state, config: RunnableConfig):
    checkpoint_ns = config["configurable"]["checkpoint_ns"]
```

## 상태 조회/갱신

```python
# 최신 상태
config = {"configurable": {"thread_id": "1"}}
graph.get_state(config)

# 특정 체크포인트
config = {"configurable": {"thread_id": "1", "checkpoint_id": "1ef..."}}
graph.get_state(config)

# 전체 이력 (최신순)
list(graph.get_state_history(config))
```

**StateSnapshot 필드** : `values`(채널 값), `next`(다음 실행 노드, `()`면 완료), `config`,
`metadata`(`source`=input/loop/update, `writes`, `step`), `created_at`, `parent_config`, `tasks`.

특정 체크포인트 찾기 :
```python
history = list(graph.get_state_history(config))
before_node_b = next(s for s in history if s.next == ("node_b",))
step_2        = next(s for s in history if s.metadata["step"] == 2)
forks         = [s for s in history if s.metadata["source"] == "update"]
interrupted   = next(s for s in history if s.tasks and any(t.interrupts for t in s.tasks))
```

### Replay (재생)
이전 `checkpoint_id`로 호출하면 그 이후 노드만 재실행(이전은 스킵). 단 **interrupt는 재생 중
항상 재트리거**된다. 자세히는 `time-travel.md`.

### Update state (상태 갱신)
`graph.update_state(config, values, as_node=...)`. **새 체크포인트를 생성**하며 원본은 안 바꾼다.
reducer가 정의된 채널은 누적(덮어쓰기 X). `as_node`로 어느 노드에서 온 갱신인지 제어 → 다음 실행 노드에 영향.

## Durability modes (지속성 모드)

성능 vs 일관성 균형. `graph.stream(..., durability="sync")`처럼 지정.

- `"exit"` : 실행 종료(성공/에러/interrupt) 시에만 영속화. 최고 성능, 중간 실패 복구 불가.
- `"async"` : 다음 스텝 실행 중 비동기 영속화 (기본). 좋은 성능+지속성, 크래시 시 미기록 소량 위험.
- `"sync"` : 다음 스텝 시작 전 동기 영속화. 높은 지속성, 약간의 성능 비용.

## 체크포인트 스토리지 최적화 (DeltaChannel)

기본은 매 super-step마다 모든 채널의 전체 값을 기록 → 장시간 스레드에서 저장량 급증.
`DeltaChannel`은 증분 delta만 저장. (langgraph>=1.2, beta. 자세히는 `pregel.md`)

## Checkpointer 라이브러리

`BaseCheckpointSaver` 인터페이스를 따른다. 구현체 :
- `langgraph-checkpoint` (기본 포함) : `InMemorySaver` (실험용)
- `langgraph-checkpoint-sqlite` : `SqliteSaver` / `AsyncSqliteSaver` (로컬)
- `langgraph-checkpoint-postgres` : `PostgresSaver` / `AsyncPostgresSaver` (프로덕션, LangSmith 사용)
- `langchain-azure-cosmosdb` : `CosmosDBSaver` (Azure)

인터페이스 메서드 : `.put`, `.put_writes`, `.get_tuple`, `.list` (async는 `.aput` 등).

자세한 사용·setup은 `checkpointers.md` 참조.

### Serializer (직렬화)
기본 `JsonPlusSerializer`(ormsgpack+JSON). Pandas 등 미지원 타입은 `pickle_fallback=True` :

```python
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
graph.compile(checkpointer=InMemorySaver(serde=JsonPlusSerializer(pickle_fallback=True)))
```

**암호화** : `EncryptedSerializer`를 `serde`에 전달. `from_pycryptodome_aes()`는
`LANGGRAPH_AES_KEY` 환경변수에서 AES 키를 읽는다.

```python
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.checkpoint.postgres import PostgresSaver

serde = EncryptedSerializer.from_pycryptodome_aes()
checkpointer = PostgresSaver.from_conn_string("postgresql://...", serde=serde)
checkpointer.setup()
```

## Memory Store (스레드 간 공유)

checkpointer는 스레드 *내부* 상태만 저장한다. 스레드를 *넘어* 정보를 공유하려면 `Store`를 쓴다.
checkpointer(스레드별)와 store(스레드 간)를 함께 컴파일한다. 자세히는 `stores.md`, `memory.md`.

```python
graph = builder.compile(checkpointer=checkpointer, store=store)
```
