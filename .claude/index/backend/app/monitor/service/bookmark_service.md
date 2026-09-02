파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agentackendpp\monitor\serviceookmark_service.py`

클래스 기능: `BookmarkService` - 북마크(`chat_bookmark` 테이블) 조회/추가/메모수정/삭제

상수: `MEMO_MAXIMUM_LENGTH`=1000, `PREVIEW_MAXIMUM_LENGTH`=500

하위 함수 기능:
- `normalize_memo(memo)`: 앞뒤 공백 제거 → 빈 문자열은 NULL(메모 없음) → 최대 길이로 절단
- `list_bookmarks_async(authorization)`: 인증 사용자의 북마크 (최신순, memo 포함)
- `upsert_bookmark_async(bookmark_request, authorization)`: 방 소유권 확인 후 upsert.
  **메모는 `COALESCE` 로 보존** — 캐시 재등록처럼 메모를 싣지 않은 요청이 기존 메모를 지우면 안 된다
- `update_bookmark_memo_async(bookmark_id, memo_request, authorization)`: 메모만 부분 수정. 남의 것이면 404
- `delete_bookmark_async(bookmark_id, authorization)`: 이미 없어도 성공 처리 (토글 연타·낙관적 UI 재시도 대비)
