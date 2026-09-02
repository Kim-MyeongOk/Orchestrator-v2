파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\main.jsx`

모듈 기능: React 앱 진입점 + 인증 게이트

`AUTH_USER_ID_STORAGE_KEY` 가 없으면 앱을 마운트하지 않고 `LOGIN_PAGE_PATH`(`/legacy/login.html`)로 보낸다.

> 이 게이트가 없으면 토큰 없이 방 목록 API 를 두드려 401 이 쌓이고, 실패 폴백으로 빈 방까지 생성된다.

로그인 상태면 `StrictMode` 로 `<App />` 을 마운트한다.
