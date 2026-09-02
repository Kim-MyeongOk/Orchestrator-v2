파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\database\table_query\chat_bookmark_query.py`

클래스 기능: `ChatBookmarkQuery` - `chat_bookmark` 테이블의 DDL 과 쿼리 모음

`TABLE_NAME`="chat_bookmark" · `CREATION_ORDER`=20 (chat_room 을 REFERENCES) · 풀=**psycopg (`%s`)**

북마크는 "방 안에서 N 번째 답변"(`agent_index`) 단위로 저장한다.
`chat_room` 에 불리언 칼럼을 두지 않는 이유 — `thread_id` 는 대화 전체를 가리켜 답변 하나를 지목할 수 없다.
`text` 는 미리보기 스냅샷 — 없으면 사이드바를 그릴 때마다 방마다 체크포인트를 통째로 열어야 한다.

상수:
- `CREATE_TABLE`: 테이블 + `idx_chat_bookmark_user_created` 인덱스 + `memo` 칼럼(`ADD COLUMN IF NOT EXISTS`).
  `memo` 의 `NULL` 은 "메모 없음" — 빈 문자열과 구분해야 upsert 시 `COALESCE` 로 기존 메모를 보존할 수 있다
- `SELECT_LIST_BY_USER`: 최신순 목록 (`completed_at` / `created_at` 을 epoch ms 로 변환)
- `UPSERT`: 같은 답변을 다시 북마크하면 미리보기만 갱신.
  **메모는 `COALESCE(EXCLUDED.memo, chat_bookmark.memo)` 로 보존** — 캐시 재등록처럼
  메모를 싣지 않은 요청이 기존 메모를 지우면 안 된다
- `UPDATE_MEMO_BY_OWNER`: 메모만 부분 수정 (PATCH)
- `DELETE_BY_OWNER`: 본인 소유만 삭제
- `DELETE_FROM_AGENT_INDEX`: 질문 수정으로 대화가 절단될 때 잘려나간 답변의 북마크 정리.
  `agent_index` 는 위치 기반이라 남겨두면 엉뚱한 답변을 가리키게 된다

사용처: `BookmarkService` · `ThreadService`(절단 시 정리)
