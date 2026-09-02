파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\constants\storageKeys.js`

모듈 기능: localStorage 키 상수 + JSON 읽기/쓰기 헬퍼

> 기존 `chat.html` 과 **같은 키**를 쓴다 — 기존 사용자의 방·북마크·설정이 그대로 승계된다.

키 목록:
- `THEME_STORAGE_KEY` / `ROOM_STORAGE_KEY` / `BOOKMARK_STORAGE_KEY`
- `USER_ID_STORAGE_KEY` / `AUTH_USER_ID_STORAGE_KEY` / `AUTH_TOKEN_STORAGE_KEY`
- `DEVELOPER_MODE_STORAGE_KEY` / `API_URL_STORAGE_KEY`
- `LOGOUT_REASON_STORAGE_KEY` : 세션 만료 사유 (재접속 시 1회 안내)
- `INPUT_DRAFT_STORAGE_KEY` : 작성 중이던 입력 (튕겨도 잃지 않도록)
- `LOGIN_PAGE_PATH` = `/legacy/login.html`

하위 함수 기능:
- `readJsonFromStorage(storageKey, fallbackValue)`: 파싱 실패(수동 편집·구버전 포맷)를 조용히 기본값으로 되돌린다
- `writeJsonToStorage(storageKey, value)`: 저장 실패(용량 초과 등)를 삼킨다
