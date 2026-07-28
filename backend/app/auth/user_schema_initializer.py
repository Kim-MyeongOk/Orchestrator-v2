from app.database.table_query_registry                  import TableQueryRegistry
from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager

##################################################
# 사용자 스키마 초기화기 (asyncpg 풀)
#
# DDL 을 여기에 두지 않고 app/database/table_query/*_query.py 에서 가져온다.
# 테이블을 추가할 때 이 파일을 고칠 필요가 없다 — 쿼리 파일 하나만 만들면 자동으로 포함된다.
# (asyncpg 풀에서 만들 테이블은 쿼리 클래스에 IS_ASYNCPG = True 를 둔다)
##################################################
class UserSchemaInitializer:
    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager) -> None:
        self.postgresql_pool_manager = postgresql_pool_manager

    async def initialize_schema_async(self) -> None:
        table_query_class_list = TableQueryRegistry.load_asyncpg_table_query_class_list()
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            for table_query_class in table_query_class_list:
                await connection.execute(table_query_class.CREATE_TABLE)
        print(f"ASYNCPG TABLE READY : {[table_query_class.TABLE_NAME for table_query_class in table_query_class_list]}", flush = True)
