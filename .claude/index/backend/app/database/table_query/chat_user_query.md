파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\database\table_query\chat_user_query.py`

클래스 기능: `ChatUserQuery` - `chat_user` 테이블의 DDL 과 쿼리 모음

`TABLE_NAME`="chat_user" · `CREATION_ORDER`=5 · `IS_ASYNCPG`=True · 풀=**asyncpg (`$1, $2`)**

> ⚠️ **이 테이블만 플레이스홀더가 다르다.** `chat_room` / `chat_bookmark` 는 psycopg 풀이라 `%s` 를 쓰고,
> `chat_user` 는 asyncpg 풀이라 `$1, $2` 를 쓴다. 섞으면 런타임에 터진다.

로그인 계정. `user_id` 는 로그인 식별자이자 채팅 스코핑 키로,
`chat_room.user_id`(TEXT) 와 같은 타입이라 방 목록/대화가 같은 ID 로 이어진다.

상수:
- `CREATE_TABLE`: `user_id`(PK) · `password_hash` · `created_at`
- `SELECT_PASSWORD_HASH`: 로그인 검증용 해시 조회
- `INSERT_IF_ABSENT`: `ON CONFLICT (user_id) DO NOTHING RETURNING TRUE`.
  조회 후 삽입이 아니라 한 문장이라 **같은 ID 로 동시에 가입 요청이 들어와도 한쪽만 성공**한다.
  중복이면 `RETURNING` 이 비어 있어 호출부가 409 로 응답한다

사용처: `UserRepository` · `UserSchemaInitializer`(DDL)
