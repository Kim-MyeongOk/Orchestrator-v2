파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agentackendpp\database	able_query\llm_thread_query.py`

클래스 기능: `LlmThreadQuery` - `llm_thread` 테이블의 DDL

`TABLE_NAME`="llm_thread" · `CREATION_ORDER`=120 · `IS_ASYNCPG`=True · 풀=**asyncpg (`$1, $2`)**

대화 스레드 목록 (Job 서비스용)

상수:
- `CREATE_TABLE`: 테이블 + 인덱스 + `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`(기존 배포 호환)

> **쿼리 상수는 아직 이 파일에 없다.** SELECT/INSERT/UPDATE 는 `app/llm/repository/chat_thread_repository.py` 에 남아 있다.
> DDL 만 먼저 모아 스키마 생성을 `TableQueryRegistry` 자동 수집으로 통일했다.
