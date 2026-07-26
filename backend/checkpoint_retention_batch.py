##################################################
# 체크포인트 Retention 독립 배치 엔트리포인트
# FastAPI lifespan 과 격리된 단독 프로세스로, 외부 인프라 크론잡에서 호출한다.
#
#   실행   : python backend/checkpoint_retention_batch.py   (프로젝트 루트 기준, .env 자동 로드)
#   크론 예 : 0 4 * * *  cd /app && .venv/bin/python backend/checkpoint_retention_batch.py
#   종료코드: 0 = 정상, 1 = 실패 (크론 알림 연동용)
#
# 환경변수 :
#   CHECKPOINT_KEEP_COUNT          스레드별 유지할 최신 체크포인트 수 (기본 20)
#   CHECKPOINT_IDLE_DAY_COUNT      유휴 스레드 판정 일수 (기본 30)
#   CHECKPOINT_DELETE_CHUNK_SIZE   분할 삭제 청크 크기 (기본 500)
#   CHECKPOINT_DELETE_SLEEP_SECOND 청크 간 슬립 초 (기본 0.05)
##################################################

import os
import sys
import json
import asyncio

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from common.database.postgresql.postgresql_configuration      import PostgresqlConfiguration
from common.database.postgresql.postgresql_pool_manager       import PostgresqlPoolManager
from app.orchestrator.service.checkpoint_retention_service    import CheckpointRetentionService


def _create_postgresql_configuration() -> PostgresqlConfiguration:
    # server.py 와 동일한 env 규약 (배치 프로세스 격리를 위해 server 모듈은 import 하지 않는다)
    return PostgresqlConfiguration(
        host                     =     os.getenv("POSTGRESQL_HOST"                    , "localhost"),
        port                     = int(os.getenv("POSTGRESQL_PORT"                    , "5432"     )),
        database_name            =     os.getenv("POSTGRESQL_DATABASE"                , os.getenv("POSTGRESQL_DATABASE_NAME", "postgres")),
        user_name                =     os.getenv("POSTGRESQL_USER"                    , os.getenv("POSTGRESQL_USER_NAME"    , "postgres")),
        password                 =     os.getenv("POSTGRESQL_PASSWORD"                , "postgres"),
        minimum_connection_count = 1,
        maximum_connection_count = 2
    )


async def execute_batch_async() -> int:
    postgresql_pool_manager = PostgresqlPoolManager(_create_postgresql_configuration())
    await postgresql_pool_manager.open_async()
    try:
        checkpoint_retention_service = CheckpointRetentionService(
            postgresql_pool_manager,
            keep_checkpoint_count    = int(os.getenv("CHECKPOINT_KEEP_COUNT"         , "20"  )),
            idle_day_count           = int(os.getenv("CHECKPOINT_IDLE_DAY_COUNT"     , "30"  )),
            delete_chunk_size        = int(os.getenv("CHECKPOINT_DELETE_CHUNK_SIZE"  , "500" )),
            chunk_sleep_second_count = float(os.getenv("CHECKPOINT_DELETE_SLEEP_SECOND", "0.05"))
        )
        retention_result = await checkpoint_retention_service.execute_retention_async()
        print(f"CHECKPOINT RETENTION COMPLETED : {json.dumps(retention_result, ensure_ascii = False)}", flush = True)
        return 0
    except Exception as exception:
        print(f"CHECKPOINT RETENTION FAILED : {exception}", file = sys.stderr, flush = True)
        return 1
    finally:
        await postgresql_pool_manager.close_async()


if __name__ == "__main__":
    sys.exit(asyncio.run(execute_batch_async()))
