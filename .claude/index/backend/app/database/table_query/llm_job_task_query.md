파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agentackendpp\database	able_query\llm_job_task_query.py`

클래스 기능: `LlmJobTaskQuery` - `llm_job_task` 테이블의 DDL

`TABLE_NAME`="llm_job_task" · `CREATION_ORDER`=160 · `IS_ASYNCPG`=True · 풀=**asyncpg (`$1, $2`)**

Job 내부 태스크(서브에이전트/도구 호출) 진행 상태

상수:
- `CREATE_TABLE`: 테이블 + 인덱스 + `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`(기존 배포 호환)

> **쿼리 상수는 아직 이 파일에 없다.** SELECT/INSERT/UPDATE 는 `app/llm/repository/job_task_repository.py` 에 남아 있다.
> DDL 만 먼저 모아 스키마 생성을 `TableQueryRegistry` 자동 수집으로 통일했다.
