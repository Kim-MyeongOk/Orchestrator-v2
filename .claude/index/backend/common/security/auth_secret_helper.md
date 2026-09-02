파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\common\security\auth_secret_helper.py`

클래스 기능: `AuthSecretHelper` - 토큰 서명용 비밀키를 **서버를 재시작해도 같은 값**으로 유지

> **왜 필요한가** : 예전에는 `os.getenv("AUTH_TOKEN_SECRET") or secrets.token_hex(32)` 로,
> 환경변수가 없으면 매 기동마다 새 비밀키를 만들었다. 그 탓에 서버를 재시작할 때마다
> 발급해 둔 토큰이 전부 서명 검증에 실패해 사용자가 로그아웃됐다
> (`POST /stream 401 Unauthorized` → 프론트가 로그인 페이지로 튕김).

해석 우선순위:
1. 환경변수 `AUTH_TOKEN_SECRET` — 운영 경로 (여러 인스턴스가 같은 키를 공유해야 하므로 파일 방식은 부적합)
2. 로컬 비밀키 파일 (기본 `.auth_token_secret`, `.gitignore` 대상) — 이전 기동에서 만든 값을 재사용
3. 새로 만들어 파일에 저장 — 최초 1회

상수: `SECRET_BYTE_COUNT`=32 (결과는 64자 16진 문자열)

하위 함수 기능:
- `_read_secret_file()`: 비밀키 파일 읽기 (없음·빈 값·읽기 실패는 `None`)
- `_write_secret_file()`: 비밀키 파일 저장. 실패해도 기동을 막지 않고 `False` 반환 (이번 프로세스만 임시 키로 동작)
- `resolve_secret(environment_secret, secret_file_path)`: 위 우선순위로 고정 비밀키 확보
