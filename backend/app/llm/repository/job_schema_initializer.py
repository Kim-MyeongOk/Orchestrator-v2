##################################################
# Job 스키마 초기화기 (asyncpg 풀)
#
# DDL 을 여기에 두지 않고 app/database/table_query/*_query.py 에서 가져온다.
# 테이블을 추가할 때 이 파일을 고칠 필요가 없다 — 쿼리 파일 하나만 만들면 자동으로 포함된다.
#
# 생성 순서는 각 쿼리 클래스의 CREATION_ORDER 가 정한다 (외래키 참조 순서).
#   llm_job(110) → llm_thread(120) → llm_job_message(130) → llm_thread_message(140)
#   → llm_job_chunk(150) → llm_job_task(160) → llm_job_event(170)
#
# 참고 : checkpoints / checkpoint_migrations 계열은 여기서 다루지 않는다.
#        LangGraph 의 MIGRATIONS 최종 스키마와 정확히 일치해야 하고 파티션 수가 런타임 변수라
#        CheckpointSchemaInitializer 가 따로 관리한다.
##################################################

from app.database.table_query_registry                  import TableQueryRegistry
from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager


class JobSchemaInitializer:
    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager) -> None:
        self.postgresql_pool_manager = postgresql_pool_manager

    async def initialize_schema_async(self) -> None:
        table_query_class_list = TableQueryRegistry.load_asyncpg_table_query_class_list()
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            for table_query_class in table_query_class_list:
                await connection.execute(table_query_class.CREATE_TABLE)
        print(f"ASYNCPG TABLE READY : {[table_query_class.TABLE_NAME for table_query_class in table_query_class_list]}", flush = True)
