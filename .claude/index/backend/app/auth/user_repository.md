파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\auth\user_repository.py`

클래스 기능: `UserRepository` - 사용자 계정(`chat_user` 테이블) 조회/등록 저장소

하위 함수 기능:
- `__init__(postgresql_pool_manager)`: PostgreSQL 커넥션 풀 주입
- `create_user_async(user_id, password_hash)`: 신규 사용자 등록 (`ChatUserQuery.INSERT_IF_ABSENT`).
  `ON CONFLICT (user_id) DO NOTHING RETURNING TRUE` 로 **중복이면 삽입하지 않고 `False`** 를 반환한다.
  조회 후 삽입이 아니라 한 문장으로 처리하므로, 같은 ID 로 동시에 가입 요청이 들어와도 한쪽만 성공한다.
  호출부(`ServerApplication.register_user_async`)는 `False` 를 받으면 `409 이미 등록된 유저입니다.` 로 응답한다.
- `get_password_hash_async(user_id)`: 로그인 검증용 비밀번호 해시 조회 (`ChatUserQuery.SELECT_PASSWORD_HASH`, 없으면 `None`)

> SQL 은 이 파일에 두지 않는다 — `app/database/table_query/chat_user_query.py` 참고.
