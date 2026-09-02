파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\api\chatApi.js`

모듈 기능: 백엔드 REST/스트리밍 API 호출 계층. 서버 응답(snake_case) ↔ 화면 모델(camelCase) 변환을 여기서 처리한다

베이스 URL 우선순위: 개발자 모드 저장값 > `.env` 의 `VITE_API_URL` > `http://localhost:8000`

하위 함수 기능:
- `getApiUrl()` / `setApiUrl()`: 백엔드 베이스 URL 조회·변경
- `getAuthToken()` / `getUserId()`: 인증 정보 조회
- `logout(logoutReasonText)`: 인증 정보를 지우고 로그인 페이지로 이동.
  사유를 주면 저장해 두었다가 재접속 시 1회 안내하고 **입력 초안을 보존**한다.
  사유가 없으면(사용자가 직접 로그아웃) 초안도 함께 지운다
- `takeLogoutReasonText()`: 저장된 로그아웃 사유를 읽고 지운다 (한 번만 안내)
- `applyRefreshedAuthToken()`: 응답의 `X-Refreshed-Auth-Token` 헤더가 오면 저장 토큰을 조용히 교체 (Silent Refresh)
- `authFetch()`: Authorization 헤더를 실어 요청 → 갱신 토큰 반영 → 401 이면 사유를 남기고 로그아웃
- `listRoomsAsync()` / `upsertRoomAsync()` / `deleteRoomAsync()`: 채팅방 CRUD
- `listBookmarksAsync()` / `upsertBookmarkAsync()` / `deleteBookmarkAsync()`: 북마크 CRUD
- `updateBookmarkMemoAsync()`: 북마크 메모만 부분 수정 (PATCH) — 명시적 사용자 조작이라 오류를 삼키지 않고 throw
- `listModelsAsync()`: 모델 목록 조회
- `listModelPresetsAsync()`: LLM 파라미터 프리셋 목록 조회 (`GET /config/presets`)
- `uploadImageAsync(imageFile)`: 이미지를 MinIO 에 업로드 (`POST /api/upload`, multipart).
  **`Content-Type` 을 직접 지정하지 않는다** — 브라우저가 multipart 경계값까지 넣어 만들어야 한다.
  실패 시 서버가 준 한국어 detail 을 담아 throw 한다 (사용자가 고칠 수 있는 오류라 삼키지 않는다)
- `getThreadMessagesAsync()` / `truncateThreadAsync()`: 체크포인트 대화 복원·절단
- `streamChatTurnAsync({ threadId, message, model, reasoningEffort, referencedText, referencedMessageIdList, presetName, signal, onStart, onReasoning, onToken, onStreamError })`:
  NDJSON 이벤트 스트림을 읽어 콜백으로 흘려보냄. 5xx 는 재시도 대상(`Error`), 4xx 는 `NonRetryableError`

예외 클래스: `NonRetryableError` - 재시도가 무의미한 오류(4xx 등)
