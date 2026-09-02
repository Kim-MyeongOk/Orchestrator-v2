파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\repository\job_schema_initializer.py`

클래스 기능: `JobSchemaInitializer` - **asyncpg 풀의 모든 테이블** DDL 실행기

> DDL 을 여기에 두지 않고 `app/database/table_query/*_query.py` 에서 가져온다.
> 테이블을 추가할 때 이 파일을 고칠 필요가 없다.

대상 (CREATION_ORDER 순): `chat_user`(5) → `llm_job`(110) → `llm_thread`(120) →
`llm_job_message`(130) → `llm_thread_message`(140) → `llm_job_chunk`(150) →
`llm_job_task`(160) → `llm_job_event`(170)

> **`UserSchemaInitializer` 는 삭제하고 여기에 통합했다.** 레지스트리 도입 후 두 초기화기가
> 같은 목록을 실행하게 되어 DDL 이 두 번 돌았다.

> `checkpoints` 계열은 다루지 않는다 — LangGraph MIGRATIONS 스키마와 파티션 템플릿이 얽혀 있어
> `CheckpointSchemaInitializer` 가 따로 관리한다.

하위 함수 기능:
- `__init__(postgresql_pool_manager)`: asyncpg 커넥션 풀 주입
- `initialize_schema_async()`: 레지스트리에서 asyncpg 테이블을 받아 순서대로 DDL 실행,
  완료 후 `ASYNCPG TABLE READY : [...]` 로그 출력
