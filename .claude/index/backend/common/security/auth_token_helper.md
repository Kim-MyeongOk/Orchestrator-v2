파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\common\security\auth_token_helper.py`

클래스 기능: `AuthTokenHelper` - HMAC-SHA256 서명 기반 **무상태** 인증 토큰 생성/검증 (외부 의존성 없이 stdlib 만 사용)

> JWT 라이브러리를 쓰지 않는다. 형식은 `base64url(payload_json).base64url(signature)` 이고
> payload 는 `{"user_id", "exp"}` 다. 서버 비밀키로 서명하므로 별도 세션 저장소가 필요 없다.
> **비밀키가 바뀌면 발급해 둔 토큰이 전부 무효가 된다** → 비밀키 고정은 `auth_secret_helper.md` 참고.

하위 함수 기능:
- `_base64url_encode()` / `_base64url_decode()`: 패딩 없는 base64url 변환
- `_sign()`: payload 세그먼트에 HMAC-SHA256 서명
- `_read_verified_payload()`: 서명·형식만 검증하고 payload 반환 (만료는 판단하지 않음)
- `create_token()`: `user_id` + TTL 로 토큰 발급
- `read_remaining_second_count()`: 남은 유효 시간(초). 무효·만료는 `None` — 슬라이딩 갱신 시점 판단용
- `verify_token()`: 서명·만료를 검증하고 `user_id` 반환. 무효/만료/형식오류는 `None`
