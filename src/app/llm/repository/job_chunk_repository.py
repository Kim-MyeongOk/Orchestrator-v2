import asyncpg
import uuid

from typing   import Dict
from typing   import Any
from datetime import datetime
from datetime import timezone
from typing   import Optional
from typing   import List

from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager
from app.llm.stream_pipeline.normalized_chunk           import NormalizedChunk

class JobChunkRepository:
    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager) -> None:
        self.postgresql_pool_manager = postgresql_pool_manager

    @staticmethod
    def _convert_record_to_dictionary(record : asyncpg.Record) -> Dict[str, Any]:
        chunk_dictionary = dict(record)
        for field_name in ("id", "run_id"):
            if chunk_dictionary.get(field_name) is not None:
                chunk_dictionary[field_name] = str(chunk_dictionary[field_name])
        if chunk_dictionary.get("created_at") is not None:
            chunk_dictionary["created_at"] = chunk_dictionary["created_at"].isoformat()
        return chunk_dictionary

    @staticmethod
    def _get_created_at(normalized_chunk : NormalizedChunk) -> datetime:
        created_at_text = f"{normalized_chunk.created_at[:-1]}+00:00" if normalized_chunk.created_at.endswith("Z") else normalized_chunk.created_at
        try:
            created_at = datetime.fromisoformat(created_at_text)
        except ValueError as exception:
            raise ValueError(f"INVALID NORMALIZED CHUNK CREATED AT : {normalized_chunk.created_at}") from exception
        return created_at.replace(tzinfo = timezone.utc) if created_at.tzinfo is None else created_at.astimezone(timezone.utc)

    @staticmethod
    async def _insert_chunk_with_connection_async(connection : asyncpg.Connection, chunk_uuid : uuid.UUID, run_id : uuid.UUID, normalized_chunk : NormalizedChunk) -> None:
        query_text = """
INSERT INTO llm_job_chunk
(
    id,
    run_id,
    seq,
    chunk_type,
    ns_list,
    ns_path,
    task_id,
    parent_task_id,
    task_link_type,
    data,
    stream_version,
    schema_version,
    projection_status,
    created_at
)
VALUES
(
    $1,
    $2,
    $3,
    $4,
    $5,
    $6,
    $7,
    $8,
    $9,
    $10,
    $11,
    $12,
    $13,
    $14
)
ON CONFLICT (run_id, seq) DO NOTHING
"""
        await connection.execute(
            query_text,
            chunk_uuid,
            run_id,
            normalized_chunk.sequence,
            normalized_chunk.chunk_type,
            normalized_chunk.namespace_list,
            normalized_chunk.namespace_path,
            normalized_chunk.task_id,
            normalized_chunk.parent_task_id,
            normalized_chunk.task_link_type,
            normalized_chunk.data_dictionary,
            normalized_chunk.stream_version,
            normalized_chunk.schema_version,
            normalized_chunk.projection_status,
            JobChunkRepository._get_created_at(normalized_chunk)
        )

    @staticmethod
    async def _get_chunk_count_with_connection_async(connection : asyncpg.Connection, run_id : uuid.UUID) -> int:
        chunk_count = await connection.fetchval("SELECT COUNT(*) FROM llm_job_chunk WHERE run_id = $1", run_id)
        return int(chunk_count)

    @staticmethod
    async def _get_last_sequence_number_with_connection_async(connection : asyncpg.Connection, run_id : uuid.UUID) -> int:
        last_sequence_number = await connection.fetchval("SELECT COALESCE(MAX(seq), 0) FROM llm_job_chunk WHERE run_id = $1", run_id)
        return int(last_sequence_number)

    async def insert_chunk_async(self, chunk_uuid : uuid.UUID, run_id : uuid.UUID, normalized_chunk : NormalizedChunk, connection : Optional[asyncpg.Connection] = None) -> None:
        if connection is not None:
            await JobChunkRepository._insert_chunk_with_connection_async(connection, chunk_uuid, run_id, normalized_chunk)
            return
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            await JobChunkRepository._insert_chunk_with_connection_async(acquired_connection, chunk_uuid, run_id, normalized_chunk)

    async def get_chunk_list_async(self, run_id : uuid.UUID) -> List[Dict[str, Any]]:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record_list = await connection.fetch("SELECT * FROM llm_job_chunk WHERE run_id = $1 ORDER BY seq ASC", run_id)
            return [JobChunkRepository._convert_record_to_dictionary(record) for record in record_list]

    async def get_chunk_list_after_sequence_async(self, run_id : uuid.UUID, sequence_number : int, limit_count : int = 500) -> List[Dict[str, Any]]:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record_list = await connection.fetch("SELECT * FROM llm_job_chunk WHERE run_id = $1 AND seq > $2 ORDER BY seq ASC LIMIT $3", run_id, sequence_number, limit_count)
            return [JobChunkRepository._convert_record_to_dictionary(record) for record in record_list]

    async def get_chunk_count_async(self, run_id : uuid.UUID, connection : Optional[asyncpg.Connection] = None) -> int:
        if connection is not None:
            return await JobChunkRepository._get_chunk_count_with_connection_async(connection, run_id)
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            return await JobChunkRepository._get_chunk_count_with_connection_async(acquired_connection, run_id)

    async def get_last_sequence_number_async(self, run_id : uuid.UUID, connection : Optional[asyncpg.Connection] = None) -> int:
        if connection is not None:
            return await JobChunkRepository._get_last_sequence_number_with_connection_async(connection, run_id)
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            return await JobChunkRepository._get_last_sequence_number_with_connection_async(acquired_connection, run_id)
