파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\database\table_query\chat_room_query.py`

클래스 기능: `ChatRoomQuery` - `chat_room` 테이블의 DDL 과 쿼리 모음

`TABLE_NAME`="chat_room" · `CREATION_ORDER`=10 (chat_bookmark 가 참조하므로 먼저 생성) · 풀=**psycopg (`%s`)**

유저별 채팅방 목록. 대화 내용은 체크포인트가 원본이므로 여기는 목록/메타와 요약 상태만 저장한다.

상수:
- `CREATE_TABLE`: 테이블 + `idx_chat_room_user_updated` 인덱스 +
  요약 칼럼 3개(`summary` / `summarized_message_count` / `summary_updated_at`)를 `ADD COLUMN IF NOT EXISTS` 로 추가
- `SELECT_LIST_BY_USER`: 인증 사용자의 방 목록 (최근 수정순)
- `SELECT_FOREIGN_OWNER_BY_THREAD`: 스레드 소유권 검증 (다른 사용자 소유면 행이 나온다 → 403)
- `SELECT_OWNED_ROOM`: 방 소유권 검증 (본인 소유가 아니거나 없으면 비어 있다)
- `SELECT_SUMMARY`: 요약문 + 반영 메시지 수
- `UPSERT`: 생성/갱신. 소유자가 다르면 `WHERE` 에서 걸러져 rowcount 0 (남의 방 갈취 방지)
- `DELETE_BY_OWNER`: 본인 소유 방만 삭제
- `UPDATE_SUMMARY` / `CLEAR_SUMMARY`: 요약 갱신 / 초기화

사용처: `RoomService` · `AuthService`(소유권) · `BookmarkService`(방 소유권) · `ConversationSummaryRepository`
