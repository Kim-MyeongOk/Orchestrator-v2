파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\common\security\auth_token_renewal_middleware.py`

클래스 기능: `AuthTokenRenewalMiddleware` - 인증 토큰 자동 연장 (Silent Refresh). Starlette `BaseHTTPMiddleware` 상속

동작:
- 인증된 요청이 지나갈 때 토큰의 남은 수명을 본다
- 남은 수명이 `ttl_second_count × renewal_ratio`(기본 0.5) 아래면 새 토큰을 발급해
  `X-Refreshed-Auth-Token` 응답 헤더로 함께 내려준다
- 프론트(`chatApi.authFetch`)가 이 헤더를 보면 저장된 토큰을 조용히 갈아끼운다 → 쓰는 동안 만료되지 않는다
- **이미 만료된 토큰은 되살리지 않는다** (그러면 만료가 사실상 무한정 미뤄진다)
- 갱신 중 예외가 나도 본 요청 응답에는 영향을 주지 않는다

> **별도 Refresh Token 을 두지 않는 이유** : 이 서비스의 토큰은 서명만으로 검증하는 무상태 토큰이고,
> Access/Refresh 를 나눠도 둘 다 같은 localStorage 에 놓여 탈취 위험이 줄지 않는다. 반면 갱신 엔드포인트·
> 회전·폐기 관리가 새로 생긴다. "쓰는 동안 만료되지 않게 한다"는 목적에는 슬라이딩 갱신으로 충분하다.

> **등록 순서 주의** : CORS 미들웨어보다 **먼저** 등록해야 CORS 가 바깥쪽에 놓여 이 헤더까지 노출 처리된다.
> 또한 `expose_headers` 에 `X-Refreshed-Auth-Token` 이 있어야 브라우저 JS 가 헤더를 읽을 수 있다.

상수: `REFRESHED_TOKEN_HEADER_NAME`="X-Refreshed-Auth-Token", `AUTHORIZATION_PREFIX`="Bearer "

하위 함수 기능:
- `__init__(application, secret, ttl_second_count, renewal_ratio)`: 비밀키·수명·갱신 임계 비율 주입
- `_extract_bearer_token()`: `Authorization: Bearer <token>` 에서 토큰만 추출 (형식이 다르면 `None`)
- `_build_refreshed_token()`: 갱신 대상이면 새 토큰 발급, 아니면 `None`
- `dispatch()`: 응답 생성 후 갱신 헤더를 덧붙임
