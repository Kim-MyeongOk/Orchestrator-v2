파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agentackendpp\database	able_query\llm_job_query.py`

클래스 기능: `LlmJobQuery` - `llm_job` 테이블의 DDL

`TABLE_NAME`="llm_job" · `CREATION_ORDER`=110 · `IS_ASYNCPG`=True · 풀=**asyncpg (`$1, $2`)**

LLM 작업(Job) 마스터. 나머지 llm_job_* 이 이 테이블을 참조한다

상수:
- `CREATE_TABLE`: 테이블 + 인덱스 + `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`(기존 배포 호환)

> **쿼리 상수는 아직 이 파일에 없다.** SELECT/INSERT/UPDATE 는 `app/llm/repository/job_repository.py` 에 남아 있다.
> DDL 만 먼저 모아 스키마 생성을 `TableQueryRegistry` 자동 수집으로 통일했다.
