파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\database\table_query_registry.py`

클래스 기능: `TableQueryRegistry` - `app/database/table_query/*_query.py` 를 자동 탐색해 테이블 정의를 모으는 레지스트리

> **새 테이블을 추가할 때 이 파일을 고칠 필요가 없다.** 폴더에 쿼리 파일 하나만 만들면 된다.
> 목록을 손으로 관리하면 파일을 만들고 등록을 잊는 실수가 반드시 생기기 때문에 자동 탐색을 쓴다.
> (이 프로젝트는 `__init__.py` 를 두지 않는 네임스페이스 패키지라 `pkgutil` 로 경로를 직접 훑는다)

## 새 테이블 추가 방법

1. `app/database/table_query/{테이블명}_query.py` 를 만든다
2. 클래스 하나에 아래를 둔다

| 속성 | 필수 | 설명 |
|---|---|---|
| `TABLE_NAME` | ✅ | 테이블 이름 |
| `CREATE_TABLE` | ✅ | DDL (CREATE TABLE / CREATE INDEX / ALTER TABLE 을 함께 넣어도 된다) |
| `CREATION_ORDER` | 권장 | 작은 값이 먼저 생성된다 (**외래키 참조 순서**). 미지정 시 100 |
| `IS_ASYNCPG` | 조건부 | asyncpg 풀을 쓰면 `True` (기본 `False` = psycopg) |

3. 쿼리 상수도 같은 클래스에 모은다 (`SELECT_…` / `INSERT_…` / `UPDATE_…` / `DELETE_…`)
4. 끝. 스키마 초기화에 자동으로 포함된다.

> ⚠️ **플레이스홀더가 풀마다 다르다.** psycopg 풀(체크포인트 DB)은 `%s`, asyncpg 풀(job 스키마 DB)은 `$1, $2` 다.
> 섞으면 런타임에 터진다.

상수: `PACKAGE_NAME`="app.database.table_query", `MODULE_NAME_SUFFIX`="_query", `DEFAULT_ORDER`=100

하위 함수 기능:
- `_get_package_directory_path()`: `table_query/` 절대 경로
- `_find_table_query_class(module)`: 모듈 안에서 `TABLE_NAME` + `CREATE_TABLE` 을 가진 클래스를 찾는다.
  임포트된 다른 클래스가 딸려 들어오지 않도록 **정의 모듈이 자기 자신인 것만** 인정한다
- `load_table_query_class_list()`: 전체 목록을 `CREATION_ORDER` 순으로 반환
- `load_psycopg_table_query_class_list()`: psycopg 풀에서 만들 테이블만
- `load_asyncpg_table_query_class_list()`: asyncpg 풀에서 만들 테이블만

## 사용처

| 호출부 | 용도 |
|---|---|
| `server.py` `_initialize_checkpointer_async()` | psycopg 테이블 DDL 실행 |
| `app/auth/user_schema_initializer.py` | asyncpg 테이블 DDL 실행 |
