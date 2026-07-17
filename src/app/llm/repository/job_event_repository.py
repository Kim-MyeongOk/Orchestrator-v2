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

class JobEventRepository:
    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager) -> None:
        self.postgresql_pool_manager = postgresql_pool_manager

    @staticmethod
    def _convert_record_to_dictionary(record : asyncpg.Record) -> Dict[str, Any]:
        event_dictionary = dict(record)
        for field_name in ("id", "run_id"):
            event_dictionary[field_name] = str(event_dictionary[field_name])
        event_dictionary["created_at"] = event_dictionary["created_at"].isoformat()
        return event_dictionary

    @staticmethod
    def _get_created_at(normalized_chunk : NormalizedChunk) -> datetime:
        created_at_text = f"{normalized_chunk.created_at[:-1]}+00:00" if normalized_chunk.created_at.endswith("Z") else normalized_chunk.created_at
        try:
            created_at = datetime.fromisoformat(created_at_text)
        except ValueError as exception:
            raise ValueError(f"INVALID NORMALIZED CHUNK CREATED AT : {normalized_chunk.created_at}") from exception
        return created_at.replace(tzinfo = timezone.utc) if created_at.tzinfo is None else created_at.astimezone(timezone.utc)

    @staticmethod
    async def _insert_event_with_connection_async(connection : asyncpg.Connection, event_uuid : uuid.UUID, run_id : uuid.UUID, normalized_chunk : NormalizedChunk) -> None:
        query_text = """
INSERT INTO llm_job_event
(
    id,
    run_id,
    seq,
    chunk_type,
    ns_path,
    data,
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
    $7
)
ON CONFLICT (run_id, seq) DO NOTHING
"""
        await connection.execute(
            query_text,
            event_uuid, run_id, normalized_chunk.sequence, normalized_chunk.chunk_type,
            normalized_chunk.namespace_path, normalized_chunk.data_dictionary, JobEventRepository._get_created_at(normalized_chunk)
        )

    @staticmethod
    async def _get_event_count_with_connection_async(connection : asyncpg.Connection, run_id : uuid.UUID) -> int:
        event_count = await connection.fetchval("SELECT COUNT(*) FROM llm_job_event WHERE run_id = $1", run_id)
        return int(event_count)

    @staticmethod
    async def _get_last_sequence_number_with_connection_async(connection : asyncpg.Connection, run_id : uuid.UUID) -> int:
        last_sequence_number = await connection.fetchval("SELECT COALESCE(MAX(seq), 0) FROM llm_job_event WHERE run_id = $1", run_id)
        return int(last_sequence_number)

    async def insert_event_async(self, event_uuid : uuid.UUID, run_id : uuid.UUID, normalized_chunk : NormalizedChunk, connection : Optional[asyncpg.Connection] = None) -> None:
        if connection is not None:
            await JobEventRepository._insert_event_with_connection_async(connection, event_uuid, run_id, normalized_chunk)
            return
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            await JobEventRepository._insert_event_with_connection_async(acquired_connection, event_uuid, run_id, normalized_chunk)

    async def get_event_list_async(self, run_id : uuid.UUID) -> List[Dict[str, Any]]:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record_list = await connection.fetch("SELECT * FROM llm_job_event WHERE run_id = $1 ORDER BY seq ASC", run_id)
            return [JobEventRepository._convert_record_to_dictionary(record) for record in record_list]

    async def get_event_list_after_sequence_async(self, run_id : uuid.UUID, sequence_number : int) -> List[Dict[str, Any]]:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record_list = await connection.fetch("SELECT * FROM llm_job_event WHERE run_id = $1 AND seq > $2 ORDER BY seq ASC", run_id, sequence_number)
            return [JobEventRepository._convert_record_to_dictionary(record) for record in record_list]

    async def get_event_count_async(self, run_id : uuid.UUID, connection : Optional[asyncpg.Connection] = None) -> int:
        if connection is not None:
            return await JobEventRepository._get_event_count_with_connection_async(connection, run_id)
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            return await JobEventRepository._get_event_count_with_connection_async(acquired_connection, run_id)

    async def get_last_sequence_number_async(self, run_id : uuid.UUID, connection : Optional[asyncpg.Connection] = None) -> int:
        if connection is not None:
            return await JobEventRepository._get_last_sequence_number_with_connection_async(connection, run_id)
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            return await JobEventRepository._get_last_sequence_number_with_connection_async(acquired_connection, run_id)
