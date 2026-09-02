파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\orchestrator\repository\checkpoint_schema_initializer.py`

클래스 기능: `CheckpointSchemaInitializer` - LangGraph 체크포인터 테이블을 thread_id HASH 파티션으로 생성

대상: `checkpoints` / `checkpoint_blobs` / `checkpoint_writes` / `checkpoint_migrations`

> **`app/database/table_query/` 규약에서 제외된 유일한 스키마다.**
> LangGraph `MIGRATIONS` 최종 스키마와 정확히 일치해야 하고, 파티션 수가 런타임 변수
> (`CHECKPOINT_PARTITION_COUNT`, 기본 8)라 DDL 이 템플릿이며,
> `AsyncPostgresSaver.setup()` 의 `CREATE INDEX CONCURRENTLY` 크래시를 피하는
> 버전 선주입 로직과 한 덩어리다. 분리하면 라이브러리 업그레이드 때 어긋난다.

**파티셔닝 전략** — 세 테이블 모두 PK 가 `thread_id` 로 시작해 `PARTITION BY HASH (thread_id)` 가
PK 제약과 호환된다. 대화 단위 조회가 지배적이라 해시 프루닝으로 스캔 범위를 1/N 로 줄인다.

**setup() 과의 공존** — `setup()` 의 마이그레이션 6~8 은 `CREATE INDEX CONCURRENTLY` 인데
PostgreSQL 은 파티션 테이블에 이를 금지한다. 그래서 최종 스키마를 직접 만들고
`checkpoint_migrations` 에 버전 행을 선주입해 `setup()` 이 전부 스킵하게 한다.

상수: `REQUIRED_TABLE_NAME_TUPLE` = ("checkpoints", "checkpoint_blobs", "checkpoint_writes")

하위 함수 기능:
- `_create_partition_ddl_text(partition_count)`: 3개 부모 테이블 각각에 HASH 파티션 N개 DDL 생성
- `_apply_missing_migrations_async(connection)`: 패키지 업그레이드로 추가된 미적용 마이그레이션을
  `CONCURRENTLY` → 일반 `CREATE INDEX` 로 치환해 선적용하고 버전 기록
- `initialize_schema_async()`: 스키마 완비 판정 후 생성. 새로 만들었으면 `True`

> ⚠️ **완비 판정은 세 테이블을 모두 확인한다.** `checkpoints` 하나만 보면 나머지 둘이 지워진 상태에서도
> 완비로 오판해 통과하고, `checkpoint_migrations` 에 버전이 차 있어 마이그레이션도 건너뛰므로
> **영원히 복구되지 않고 매 요청이 `UndefinedTable: checkpoint_blobs` 로 실패**한다.
> 하나라도 빠지면 DDL 을 다시 실행한다 (전부 `IF NOT EXISTS` 라 재실행 안전).
