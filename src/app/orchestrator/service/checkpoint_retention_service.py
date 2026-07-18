##################################################
# 체크포인트 Retention 가드레일 서비스
# PostgreSQL 체크포인터(checkpoints / checkpoint_blobs / checkpoint_writes)의
# 무한 누적을 막는 두 가지 정리 로직을 제공한다.
#
#   ① prune_excess_checkpoints_async : 스레드별 최신 N개(기본 20)만 남기고 과거 버전 슬라이싱
#      - 대화 재개에는 최신 체크포인트만 필요하므로 N개 유지는 복원 기능에 영향이 없다
#      - 대용량 BYTEA 를 담는 checkpoint_blobs 는 잔존 체크포인트가 참조하는 최소 버전보다
#        오래된 고아 버전을 함께 GC 한다 (이걸 안 지우면 용량 절감 효과가 없다)
#   ② purge_idle_threads_async : 마지막 체크포인트가 idle_day_count(기본 30일) 이전인
#      유휴 스레드의 체크포인트 3테이블 전체 삭제
#      - checkpoints 테이블에는 created_at 컬럼이 없으므로 체크포인트 JSONB 의 'ts'
#        (LangGraph 가 기록하는 ISO 타임스탬프)를 기준으로 판정한다
#
# [락 회피 원칙]
# 모든 삭제는 LIMIT delete_chunk_size(기본 500) 단위 분할 삭제 + 청크 간 미세 슬립으로
# 수행하여 장시간 row lock / WAL 폭주로 실시간 API 요청이 블로킹되지 않게 한다.
# 파티션 테이블에서는 ctid 가 파티션 간 유일하지 않으므로 반드시 PK 배열로 삭제한다.
#
# [실행 주체]
# FastAPI lifespan 이 아니라 독립 배치 엔트리포인트(src/checkpoint_retention_batch.py)에서
# 외부 크론잡으로 호출된다.
##################################################

import asyncio

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing   import Any
from typing   import Dict

from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager


class CheckpointRetentionService:
    # 스레드별 초과 체크포인트 선별 : checkpoint_id 는 uuid6(시간 정렬 가능)이라 문자열 내림차순 = 최신순
    SELECT_EXCESS_CHECKPOINT_SQL = """
WITH ranked_checkpoint AS (
    SELECT thread_id, checkpoint_ns, checkpoint_id,
           ROW_NUMBER() OVER (PARTITION BY thread_id, checkpoint_ns ORDER BY checkpoint_id DESC) AS recency_rank
    FROM checkpoints
)
SELECT thread_id, checkpoint_ns, checkpoint_id
FROM ranked_checkpoint
WHERE recency_rank > $1
LIMIT $2
"""

    DELETE_CHECKPOINT_BY_KEY_SQL = """
DELETE FROM checkpoints
WHERE (thread_id, checkpoint_ns, checkpoint_id) IN (SELECT * FROM unnest($1::text[], $2::text[], $3::text[]))
"""

    DELETE_WRITE_BY_CHECKPOINT_KEY_SQL = """
DELETE FROM checkpoint_writes
WHERE (thread_id, checkpoint_ns, checkpoint_id) IN (SELECT * FROM unnest($1::text[], $2::text[], $3::text[]))
"""

    # 고아 블롭 선별 : 잔존 체크포인트들의 channel_versions 가 참조하는 채널별 최소 버전보다
    # 오래된 블롭은 어떤 체크포인트도 참조하지 않는다 (버전 문자열은 32자리 zero-pad 라 사전순 = 크기순)
    SELECT_ORPHAN_BLOB_SQL = """
WITH referenced_minimum AS (
    SELECT checkpoint_row.thread_id, checkpoint_row.checkpoint_ns,
           channel_version.key AS channel, MIN(channel_version.value) AS minimum_version
    FROM checkpoints AS checkpoint_row,
         jsonb_each_text(checkpoint_row.checkpoint -> 'channel_versions') AS channel_version
    GROUP BY checkpoint_row.thread_id, checkpoint_row.checkpoint_ns, channel_version.key
)
SELECT blob_row.thread_id, blob_row.checkpoint_ns, blob_row.channel, blob_row.version
FROM checkpoint_blobs AS blob_row
JOIN referenced_minimum ON referenced_minimum.thread_id     = blob_row.thread_id
                       AND referenced_minimum.checkpoint_ns = blob_row.checkpoint_ns
                       AND referenced_minimum.channel       = blob_row.channel
WHERE blob_row.version < referenced_minimum.minimum_version
LIMIT $1
"""

    DELETE_BLOB_BY_KEY_SQL = """
DELETE FROM checkpoint_blobs
WHERE (thread_id, checkpoint_ns, channel, version) IN (SELECT * FROM unnest($1::text[], $2::text[], $3::text[], $4::text[]))
"""

    # 유휴 스레드 판정 : 스레드의 가장 최근 체크포인트 ts 가 컷오프 이전이면 전체 삭제 대상
    SELECT_IDLE_THREAD_SQL = """
SELECT thread_id
FROM checkpoints
GROUP BY thread_id
HAVING MAX((checkpoint ->> 'ts')::timestamptz) < $1
"""

    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager, keep_checkpoint_count : int = 20, idle_day_count : int = 30, delete_chunk_size : int = 500, chunk_sleep_second_count : float = 0.05) -> None:
        if keep_checkpoint_count < 1:
            raise ValueError(f"INVALID KEEP CHECKPOINT COUNT : {keep_checkpoint_count}")
        if idle_day_count < 1:
            raise ValueError(f"INVALID IDLE DAY COUNT : {idle_day_count}")
        if delete_chunk_size < 1:
            raise ValueError(f"INVALID DELETE CHUNK SIZE : {delete_chunk_size}")
        if chunk_sleep_second_count < 0:
            raise ValueError(f"INVALID CHUNK SLEEP SECOND COUNT : {chunk_sleep_second_count}")
        self.postgresql_pool_manager  = postgresql_pool_manager
        self.keep_checkpoint_count    = keep_checkpoint_count
        self.idle_day_count           = idle_day_count
        self.delete_chunk_size        = delete_chunk_size
        self.chunk_sleep_second_count = chunk_sleep_second_count

    @staticmethod
    def _extract_deleted_count(command_status_text : str) -> int:
        # asyncpg 의 execute() 는 "DELETE 123" 형태의 커맨드 상태 문자열을 반환한다
        return int(command_status_text.split()[-1])

    async def _sleep_between_chunks_async(self) -> None:
        if self.chunk_sleep_second_count > 0:
            await asyncio.sleep(self.chunk_sleep_second_count)

    async def prune_excess_checkpoints_async(self) -> Dict[str, Any]:
        # 가드레일 ① : 스레드(+네임스페이스)별 최신 N개만 남기고 초과분을 청크 단위로 슬라이싱한다
        deleted_checkpoint_count = 0
        deleted_write_count      = 0
        deleted_blob_count       = 0
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            while True:
                excess_row_list = await connection.fetch(CheckpointRetentionService.SELECT_EXCESS_CHECKPOINT_SQL, self.keep_checkpoint_count, self.delete_chunk_size)
                if not excess_row_list:
                    break
                thread_id_list     = [excess_row["thread_id"]     for excess_row in excess_row_list]
                checkpoint_ns_list = [excess_row["checkpoint_ns"] for excess_row in excess_row_list]
                checkpoint_id_list = [excess_row["checkpoint_id"] for excess_row in excess_row_list]
                deleted_write_count      += CheckpointRetentionService._extract_deleted_count(await connection.execute(CheckpointRetentionService.DELETE_WRITE_BY_CHECKPOINT_KEY_SQL, thread_id_list, checkpoint_ns_list, checkpoint_id_list))
                deleted_checkpoint_count += CheckpointRetentionService._extract_deleted_count(await connection.execute(CheckpointRetentionService.DELETE_CHECKPOINT_BY_KEY_SQL,       thread_id_list, checkpoint_ns_list, checkpoint_id_list))
                await self._sleep_between_chunks_async()

            # 초과 체크포인트 삭제 후 : 더 이상 참조되지 않는 과거 버전 블롭을 청크 단위로 GC 한다
            while True:
                orphan_blob_row_list = await connection.fetch(CheckpointRetentionService.SELECT_ORPHAN_BLOB_SQL, self.delete_chunk_size)
                if not orphan_blob_row_list:
                    break
                deleted_blob_count += CheckpointRetentionService._extract_deleted_count(await connection.execute(
                    CheckpointRetentionService.DELETE_BLOB_BY_KEY_SQL,
                    [orphan_blob_row["thread_id"]     for orphan_blob_row in orphan_blob_row_list],
                    [orphan_blob_row["checkpoint_ns"] for orphan_blob_row in orphan_blob_row_list],
                    [orphan_blob_row["channel"]       for orphan_blob_row in orphan_blob_row_list],
                    [orphan_blob_row["version"]       for orphan_blob_row in orphan_blob_row_list]
                ))
                await self._sleep_between_chunks_async()
        return {"deleted_checkpoint_count" : deleted_checkpoint_count, "deleted_write_count" : deleted_write_count, "deleted_blob_count" : deleted_blob_count}

    async def purge_idle_threads_async(self) -> Dict[str, Any]:
        # 가드레일 ② : 마지막 체크포인트가 idle_day_count 일 이전인 유휴 스레드를 3테이블에서 전체 삭제한다
        idle_cutoff_at       = datetime.now(timezone.utc) - timedelta(days = self.idle_day_count)
        purged_row_count     = 0
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            idle_thread_row_list = await connection.fetch(CheckpointRetentionService.SELECT_IDLE_THREAD_SQL, idle_cutoff_at)
            idle_thread_id_list  = [idle_thread_row["thread_id"] for idle_thread_row in idle_thread_row_list]
            for table_name, primary_key_columns in (("checkpoint_writes", "thread_id, checkpoint_ns, checkpoint_id, task_id, idx"), ("checkpoint_blobs", "thread_id, checkpoint_ns, channel, version"), ("checkpoints", "thread_id, checkpoint_ns, checkpoint_id")):
                while True:
                    # PK 셀프 서브쿼리 + LIMIT : 유휴 스레드 행을 청크 단위로만 잡아 락 점유를 짧게 유지한다
                    command_status_text = await connection.execute(
                        f"DELETE FROM {table_name} WHERE ({primary_key_columns}) IN (SELECT {primary_key_columns} FROM {table_name} WHERE thread_id = ANY($1::text[]) LIMIT $2)",
                        idle_thread_id_list, self.delete_chunk_size
                    )
                    chunk_deleted_count = CheckpointRetentionService._extract_deleted_count(command_status_text)
                    purged_row_count   += chunk_deleted_count
                    if chunk_deleted_count < self.delete_chunk_size:
                        break
                    await self._sleep_between_chunks_async()
        return {"idle_thread_count" : len(idle_thread_id_list), "purged_row_count" : purged_row_count, "idle_cutoff_at" : idle_cutoff_at.isoformat()}

    async def execute_retention_async(self) -> Dict[str, Any]:
        # 배치 1회 실행 : 유휴 스레드 정리 → 잔존 스레드 초과분 슬라이싱 순서로 수행한다
        purge_result = await self.purge_idle_threads_async()
        prune_result = await self.prune_excess_checkpoints_async()
        return {"purge" : purge_result, "prune" : prune_result}
