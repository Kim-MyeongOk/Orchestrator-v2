##################################################
# 체크포인트 스키마 초기화기
# LangGraph PostgreSQL 체크포인터(langgraph-checkpoint-postgres>=3.1.0,<4)의
# 테이블을 thread_id HASH 파티션으로 미리 생성한다.
#
# [파티셔닝 전략]
# - checkpoints / checkpoint_blobs / checkpoint_writes 3개 테이블 모두 PK 가
#   thread_id 로 시작하므로 PARTITION BY HASH (thread_id) 가 PK 제약과 호환된다.
# - 대화(thread) 단위 조회가 지배적이므로 해시 파티션 프루닝으로 스캔 범위를
#   1/N 로 줄인다. (파티션 수는 CHECKPOINT_PARTITION_COUNT, 기본 8)
#
# [AsyncPostgresSaver.setup() 과의 공존 — 중요]
# setup() 의 마이그레이션 6~8은 CREATE INDEX CONCURRENTLY 인데, PostgreSQL 은
# 파티션 테이블에 CONCURRENTLY 인덱스 생성을 금지하므로 파티션 테이블만 먼저
# 만들어 두면 setup() 이 크래시한다. 따라서 여기서 최종 스키마 전체(테이블 +
# 일반 CREATE INDEX)를 직접 생성하고 checkpoint_migrations 에 버전 행을
# 선주입하여 setup() 이 전부 스킵하도록 만든다. 버전 수는 패키지의 MIGRATIONS
# 리스트 길이로 동적 계산하므로, 패키지 업그레이드로 신규 마이그레이션이 추가되면
# setup() 이 그것만 이어서 적용한다.
##################################################

from langgraph.checkpoint.postgres.base import MIGRATIONS

from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager


class CheckpointSchemaInitializer:
    # langgraph-checkpoint-postgres 3.1.0 의 MIGRATIONS 최종 스키마와 동일해야 한다
    PARTITIONED_SCHEMA_DDL_TEMPLATE = """
CREATE TABLE IF NOT EXISTS checkpoint_migrations
(
    v INTEGER PRIMARY KEY
);

-- 체크포인트 마스터 (그래프 슈퍼스텝 단위 상태 스냅샷)
CREATE TABLE IF NOT EXISTS checkpoints
(
    thread_id            TEXT  NOT NULL,
    checkpoint_ns        TEXT  NOT NULL DEFAULT '',
    checkpoint_id        TEXT  NOT NULL,
    parent_checkpoint_id TEXT,
    type                 TEXT,
    checkpoint           JSONB NOT NULL,
    metadata             JSONB NOT NULL DEFAULT '{{}}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
) PARTITION BY HASH (thread_id);

-- 채널 값 블롭 (대용량 상태 값 분리 저장)
CREATE TABLE IF NOT EXISTS checkpoint_blobs
(
    thread_id     TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel       TEXT NOT NULL,
    version       TEXT NOT NULL,
    type          TEXT NOT NULL,
    blob          BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
) PARTITION BY HASH (thread_id);

-- 펜딩 쓰기 (슈퍼스텝 중간 노드 산출물)
CREATE TABLE IF NOT EXISTS checkpoint_writes
(
    thread_id     TEXT    NOT NULL,
    checkpoint_ns TEXT    NOT NULL DEFAULT '',
    checkpoint_id TEXT    NOT NULL,
    task_id       TEXT    NOT NULL,
    idx           INTEGER NOT NULL,
    channel       TEXT    NOT NULL,
    type          TEXT,
    blob          BYTEA   NOT NULL,
    task_path     TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
) PARTITION BY HASH (thread_id);

{partition_ddl_text}

-- setup() 마이그레이션 6~8 의 CONCURRENTLY 인덱스를 일반 인덱스로 대체 생성
CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx       ON checkpoints (thread_id);
CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx  ON checkpoint_blobs (thread_id);
CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx ON checkpoint_writes (thread_id);
"""

    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager, partition_count : int = 8) -> None:
        if partition_count < 1:
            raise ValueError(f"INVALID CHECKPOINT PARTITION COUNT : {partition_count}")
        self.postgresql_pool_manager = postgresql_pool_manager
        self.partition_count         = partition_count

    @staticmethod
    def _create_partition_ddl_text(partition_count : int) -> str:
        # 3개 파티션 부모 각각에 HASH 파티션 N개를 생성하는 DDL 을 만든다
        partition_ddl_list = []
        for table_name in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
            for partition_index in range(partition_count):
                partition_ddl_list.append(
                    f"CREATE TABLE IF NOT EXISTS {table_name}_p{partition_index} PARTITION OF {table_name} "
                    f"FOR VALUES WITH (MODULUS {partition_count}, REMAINDER {partition_index});"
                )
        return "\n".join(partition_ddl_list)

    async def initialize_schema_async(self) -> bool:
        # 반환값 : 이번 호출에서 파티션 스키마를 새로 생성했으면 True
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            # 이미 checkpoints 테이블이 존재하면(파티션 여부 무관) 손대지 않고 setup() 에 위임한다
            # (기존 비파티션 설치본과의 호환 — 파티션 전환은 데이터 이관이 필요한 운영 작업이다)
            existing_table_kind = await connection.fetchval("SELECT relkind FROM pg_class WHERE relname = 'checkpoints' AND relnamespace = 'public'::regnamespace")
            if existing_table_kind is not None:
                return False
            async with connection.transaction():
                partition_ddl_text = CheckpointSchemaInitializer._create_partition_ddl_text(self.partition_count)
                await connection.execute(CheckpointSchemaInitializer.PARTITIONED_SCHEMA_DDL_TEMPLATE.format(partition_ddl_text = partition_ddl_text))
                # 마이그레이션 버전 선주입 : setup() 이 기존 마이그레이션을 전부 스킵하게 한다
                for migration_version in range(len(MIGRATIONS)):
                    await connection.execute("INSERT INTO checkpoint_migrations (v) VALUES ($1) ON CONFLICT (v) DO NOTHING", migration_version)
            return True
