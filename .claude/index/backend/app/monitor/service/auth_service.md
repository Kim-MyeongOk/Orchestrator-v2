파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\monitor\service\auth_service.py`

클래스 기능: `AuthService` - 사용자 등록/로그인/토큰 검증/스레드 소유권 검증

> `server.py` 에서 분리했다. **다른 모니터 서비스들이 모두 이 서비스를 주입받아** 인증을 위임한다.

상수: `AUTHORIZATION_PREFIX`="Bearer ", `MINIMUM_PASSWORD_LENGTH`=4,
`DUPLICATE_USER_MESSAGE`="이미 등록된 유저입니다."

하위 함수 기능:
- `issue_token(user_id)`: HMAC 서명 토큰 발급
- `require_authenticated_user_id(authorization)`: `Bearer` 헤더 검증 후 user_id 반환 (없거나 무효면 401)
- `assert_thread_accessible_async(user_id, thread_id)`: 남이 소유한 스레드면 403.
  미등록(신규)·본인 소유 스레드는 허용한다
- `register_user_async(register_request)`: 중복 ID 는 409(한국어 안내), 검증 실패는 400.
  응답에 user_id 를 되싣지 않는다 — 가입 API 로 계정 존재 여부를 캐낼 수 없게 하기 위함
- `login_user_async(login_request)`: ID 없음과 비밀번호 불일치를 구분하지 않고 모두 401
