# Checkpointers

원문 : https://docs.langchain.com/oss/python/langgraph/checkpointers

체크포인터는 super-step마다 그래프 상태 스냅샷을 **스레드** 단위로 저장한다. (개념·상태 조회·durability·
serializer는 `persistence.md`와 동일하므로 여기서는 **커스텀 체크포인터 구현**을 중심으로 정리한다.)

## 라이브러리

- `langgraph-checkpoint` (기본 포함) : `InMemorySaver`
- `langgraph-checkpoint-sqlite` : `SqliteSaver` / `AsyncSqliteSaver`
- `langgraph-checkpoint-postgres` : `PostgresSaver` / `AsyncPostgresSaver` (프로덕션)
- `langchain-azure-cosmosdb` : `CosmosDBSaver`

비동기 실행(`ainvoke`/`astream`)이면 async 버전(`InMemorySaver`, `AsyncSqliteSaver`, `AsyncPostgresSaver`)을 쓴다.

## 커스텀 체크포인터 만들기 (asyncpg 등 자체 백엔드)

영속성 계층은 두 스토리지 추상화 위에 있다.
- **Checkpoints 테이블** : super-step당 1 row. 직렬화된 그래프 상태(`channel_values`,
  `channel_versions`, `versions_seen`) + 부모 체크포인트 링크.
- **Writes 테이블** : super-step 내 노드 출력당 1 row. `(task_id, channel, value)` 튜플.

### 기본 계약 : `BaseCheckpointSaver` 5개 메서드 (모두 필수)

```python
from langgraph.checkpoint.base import (
    BaseCheckpointSaver, ChannelVersions, Checkpoint, CheckpointMetadata, CheckpointTuple,
)

class MyCheckpointer(BaseCheckpointSaver):
    async def aput(self, config, checkpoint, metadata, new_versions) -> RunnableConfig: ...
    async def aput_writes(self, config, writes, task_id, task_path="") -> None: ...
    async def aget_tuple(self, config) -> CheckpointTuple | None: ...
    async def alist(self, config, *, filter=None, before=None, limit=None): ...
        yield   # async generator
    async def adelete_thread(self, thread_id) -> None: ...
```

### 메서드별 요점

**aput** : 체크포인트 1 row 저장, 저장된 `checkpoint_id`를 담은 config 반환.
- `self.serde.dumps_typed(checkpoint)`로 직렬화 (delta channel의 `_DeltaSnapshot` blob 포함).
- `metadata`는 **전부 저장** (미지의 키 제거 금지 — 마이너 릴리스에서 새 필드 추가됨).
- `config["configurable"].get("checkpoint_id")`를 부모 ID로 저장 → `get_tuple`의 `parent_config` 채움.

**aput_writes** : 현재 super-step의 단일 task 노드 출력 rows 저장.
- `WRITES_IDX_MAP`(from `langgraph.checkpoint.base`)으로 특수 채널(`__error__`, `__interrupt__` 등)을
  예약된 음수 인덱스에 매핑해 일반 인덱스와 충돌 방지.

**aget_tuple** : config에 `checkpoint_id`가 있으면 그 체크포인트를, 없으면 최신을 반환.
**두 경로 모두 정확해야 한다.** 특히 specific-id 경로는 time travel과 **delta channel 재구성**에서
매 호출 사용된다 — 깨지면 delta channel 상태가 조용히 손상된다.

```python
if checkpoint_id:
    row = await db.fetchone("... WHERE thread_id=? AND checkpoint_ns=? AND checkpoint_id=?", ...)
else:
    row = await db.fetchone("... ORDER BY checkpoint_id DESC LIMIT 1", ...)
# writes도 함께 조회 → pending_writes
return CheckpointTuple(config=..., checkpoint=..., metadata=..., parent_config=..., pending_writes=...)
```

**alist** : 스레드의 체크포인트를 최신순 반환. `before`(그 config의 checkpoint_id보다 오래된 것만), `limit` 준수.
**adelete_thread** : 스레드의 모든 체크포인트 + writes rows 삭제.

### 권장 스키마 (SQL)

```sql
CREATE TABLE checkpoints (
    thread_id            TEXT NOT NULL,
    checkpoint_ns        TEXT NOT NULL DEFAULT '',
    checkpoint_id        TEXT NOT NULL,   -- ULID, 사전순 정렬 가능(최신이 큼)
    parent_checkpoint_id TEXT,
    type                 TEXT,
    checkpoint           BYTEA,
    metadata             JSONB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
CREATE TABLE writes (
    thread_id     TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id       TEXT NOT NULL,
    task_path     TEXT NOT NULL DEFAULT '',
    idx           INTEGER NOT NULL,
    channel       TEXT NOT NULL,
    type          TEXT,
    value         BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, task_path, idx)
);
```

`checkpoint_id`가 ULID라 사전순 정렬됨 → "최신"은 `ORDER BY checkpoint_id DESC LIMIT 1`,
"id로 조회"는 PK 동등 조회. **id 직접 조회가 O(1)이어야 한다** (스레드 전체 스캔 설계 회피).

### 직렬화
항상 `self.serde`(기본 `JsonPlusSerializer`) 사용. `_DeltaSnapshot`(msgpack ext code 7), Pydantic v2,
dataclass, numpy, datetime, enum 등을 자동 처리. 커스텀 serializer는 `_DeltaSnapshot` 라운드트립 보장 필요.

### 확장 능력 (선택, Agent Server 기능 활성화)

| 메서드 | 활성화 기능 |
|---|---|
| `adelete_for_runs` | multitask 롤백 |
| `acopy_thread` | 효율적 스레드 fork |
| `aprune` | 스레드 이력 pruning |
| `aget_delta_channel_history` | 효율적 delta channel 재구성 |

Agent Server는 시작 시 구현된 능력을 자동 감지해 해당 기능을 켠다.

### Delta channel 지원 (beta)

`DeltaChannel`은 체크포인트 blob에 sentinel(`MISSING`)만 저장하고, 상태는 조상(ancestor) writes를
reducer로 재생해 재구성한다. `messages`처럼 누적되는 채널의 blob을 O(N)→O(1)로 만든다.

로드 시 LangGraph가 `saver.get_delta_channel_history(config, channels)`를 호출해 채널별
`writes`(조상 체인의 모든 쓰기, 가장 가까운 스냅샷까지, 오래된 것부터)와 선택적 `seed`(가장 가까운
`_DeltaSnapshot` blob)를 받는다. 기본 구현은 `get_tuple`로 조상을 한 단계씩 걷는다(정확한 by-id 조회
필수). 백엔드가 쿼리를 잘 지원하면 `aget_delta_channel_history`를 오버라이드해 2개 쿼리로 최적화한다.

**Pruning 주의** : delta channel 상태는 단일 체크포인트에 자족적이지 않다. 살아남을 체크포인트의 delta
채널이 의존하는 write rows를 삭제하면 안 된다. (조상 체인 walk 후 보호, 또는 pruning 전 스냅샷 강제, 또는 미적용)

### Conformance 테스트

```bash
pip install langgraph-checkpoint-conformance
```

```python
from langgraph.checkpoint.conformance import checkpointer_test, validate

@checkpointer_test(name="MyCheckpointer")
async def my_checkpointer():
    async with MyCheckpointer.create() as saver:
        yield saver

report = await validate(my_checkpointer)
report.print_report()
if not report.passed_all_base():
    raise RuntimeError("Checkpointer failed conformance suite")
```

5개 base 메서드 + delta channel 등 확장 능력을 검증. CI에서 배포 전 실행 권장.
