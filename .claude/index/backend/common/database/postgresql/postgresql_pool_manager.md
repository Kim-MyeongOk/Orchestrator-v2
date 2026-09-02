파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\common\database\postgresql\postgresql_pool_manager.py`

클래스 기능: `PostgresqlPoolManager` - PostgreSQL 비동기 연결 풀 관리

하위 함수 기능:
- `__init__()`: 풀 설정 및 초기화
- `get_pool_async()`: asyncpg 커넥션 풀 반환
- `close_async()`: 풀 연결 종료
- `execute_query_async()`: SQL 쿼리 실행 (SELECT)
- `execute_mutation_async()`: SQL 변경문 실행 (INSERT/UPDATE/DELETE)
