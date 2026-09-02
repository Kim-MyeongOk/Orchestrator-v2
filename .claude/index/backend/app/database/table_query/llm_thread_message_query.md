파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agentackendpp\database	able_query\llm_thread_message_query.py`

클래스 기능: `LlmThreadMessageQuery` - `llm_thread_message` 테이블의 DDL

`TABLE_NAME`="llm_thread_message" · `CREATION_ORDER`=140 · `IS_ASYNCPG`=True · 풀=**asyncpg (`$1, $2`)**

스레드에 확정 저장된 메시지 (턴/순서 단위)

상수:
- `CREATE_TABLE`: 테이블 + 인덱스 + `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`(기존 배포 호환)

> **쿼리 상수는 아직 이 파일에 없다.** SELECT/INSERT/UPDATE 는 `app/llm/repository/thread_message_repository.py` 에 남아 있다.
> DDL 만 먼저 모아 스키마 생성을 `TableQueryRegistry` 자동 수집으로 통일했다.
