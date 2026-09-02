파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\public\legacy\login.html`

모듈 기능: 로그인 / 회원가입 페이지. React 앱과 **분리된 단독 HTML**이며 번들을 거치지 않는다
(React 앱은 인증 정보가 없으면 마운트 자체를 하지 않고 이 페이지로 보낸다 — `main.jsx` 인증 게이트 참고)

API 베이스 결정 순서:
1. React 앱 개발자 모드에서 저장한 API URL (`orchestrator_chat_api_url`)
2. 백엔드가 이 페이지를 직접 서빙 중이면 그 origin (동일 오리진 배포)
3. 그 외(Vite 개발 서버 5173 · `file://`) 는 `http://localhost:8000` 폴백

> Vite 가 서빙할 때 ②를 그대로 쓰면 5173 으로 요청이 나가 404 가 되므로 개발 서버 포트는 제외한다.

**중복 ID 회원가입 처리**
- 서버가 `409` 를 주면 공용 메시지 줄 대신 **ID 입력칸 바로 아래**에 빨간 안내를 붙이고 테두리를 붉게 바꾼다
  (어느 칸을 고쳐야 하는지 바로 보이도록)
- 문구는 `DUPLICATE_USER_MESSAGE` = "이미 등록된 유저입니다." — 백엔드 `ServerApplication.DUPLICATE_USER_MESSAGE` 와 동일
- ID 를 고치기 시작하거나 탭을 전환하면 경고를 걷는다
- 경고 시 ID 칸에 포커스를 주고 기존 값을 선택해 둔다 (바로 다른 ID 를 타이핑할 수 있게)

하위 함수 기능:
- `switchMode(mode)`: 로그인/회원가입 탭 전환 (비밀번호 확인 칸 노출, 버튼 문구, 탭 스타일)
- `showMessage(text, isError)` / `hideMessage()`: 폼 하단 공용 메시지 줄
- `showUserIdError(text)` / `clearUserIdError()`: ID 칸 전용 인라인 경고 + 테두리 강조 (`aria-invalid` 포함)
- `friendlyError(statusCode, detailText)`: 상태 코드 → 한국어 안내 매핑 (401 / 409 / 400 / 기타)
- `isDuplicateUserError(statusCode, detailText)`: 중복 ID 오류 판별 (409, 또는 400 + "이미 등록된" 문구)
- `enterChat(userId, token)`: 토큰·사용자 ID 를 localStorage 에 저장하고 React 앱(`/`)으로 이동
- `onSubmit(event)`: 클라이언트 검증(필수값·4자 이상·비밀번호 확인 일치) 후 `/auth/register` 또는 `/auth/login` 호출
