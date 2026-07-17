import asyncpg
import uuid

from typing   import Dict
from typing   import Any
from datetime import datetime
from datetime import timezone
from typing   import List
from typing   import Optional

from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager

class JobMessageRepository:
    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager) -> None:
        self.postgresql_pool_manager = postgresql_pool_manager

    @staticmethod
    def _convert_record_to_dictionary(record : asyncpg.Record) -> Dict[str, Any]:
        message_dictionary = dict(record)
        for field_name in ("id", "run_id", "thread_id"):
            message_dictionary[field_name] = str(message_dictionary[field_name])
        message_dictionary["created_at"] = message_dictionary["created_at"].isoformat()
        return message_dictionary

    @staticmethod
    def _get_created_at(merged_message_dictionary : Dict[str, Any]) -> datetime:
        created_at_value = merged_message_dictionary.get("created_at")
        if created_at_value is None:
            return datetime.now(timezone.utc)
        if isinstance(created_at_value, datetime):
            created_at = created_at_value
        elif isinstance(created_at_value, str):
            created_at_text = f"{created_at_value[:-1]}+00:00" if created_at_value.endswith("Z") else created_at_value
            try:
                created_at = datetime.fromisoformat(created_at_text)
            except ValueError as exception:
                raise ValueError(f"INVALID MESSAGE CREATED AT : {created_at_value}") from exception
        else:
            raise ValueError(f"INVALID MESSAGE CREATED AT : {created_at_value}")
        return created_at.replace(tzinfo = timezone.utc) if created_at.tzinfo is None else created_at.astimezone(timezone.utc)

    @staticmethod
    async def _insert_message_with_connection_async(connection : asyncpg.Connection, message_uuid : uuid.UUID, run_id : uuid.UUID, thread_id : uuid.UUID, merged_message_dictionary : Dict[str, Any]) -> None:
        query_text = """
INSERT INTO llm_job_message
(
    id,
    run_id,
    thread_id,
    message_id,
    ns_path,
    task_id,
    parent_task_id,
    message_metadata,
    message_type,
    tool_call_id,
    agent_name,
    is_root_message,
    role,
    content,
    tool_call_list,
    usage,
    response_metadata,
    seq_first,
    seq_last,
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
    $14,
    $15,
    $16,
    $17,
    $18,
    $19,
    $20
)
ON CONFLICT (run_id, ns_path, message_id) DO UPDATE
SET
    content           = CASE WHEN EXCLUDED.seq_last >= llm_job_message.seq_last THEN EXCLUDED.content ELSE llm_job_message.content END,
    tool_call_list    = CASE WHEN EXCLUDED.seq_last >= llm_job_message.seq_last THEN EXCLUDED.tool_call_list ELSE llm_job_message.tool_call_list END,
    usage             = CASE WHEN EXCLUDED.seq_last >= llm_job_message.seq_last THEN EXCLUDED.usage ELSE llm_job_message.usage END,
    response_metadata = CASE WHEN EXCLUDED.seq_last >= llm_job_message.seq_last THEN EXCLUDED.response_metadata ELSE llm_job_message.response_metadata END,
    task_id           = COALESCE(EXCLUDED.task_id, llm_job_message.task_id),
    parent_task_id    = COALESCE(EXCLUDED.parent_task_id, llm_job_message.parent_task_id),
    message_metadata  = COALESCE(EXCLUDED.message_metadata, llm_job_message.message_metadata),
    message_type      = COALESCE(EXCLUDED.message_type, llm_job_message.message_type),
    tool_call_id      = COALESCE(EXCLUDED.tool_call_id, llm_job_message.tool_call_id),
    agent_name        = COALESCE(EXCLUDED.agent_name, llm_job_message.agent_name),
    is_root_message   = EXCLUDED.is_root_message,
    seq_first         = LEAST(llm_job_message.seq_first, EXCLUDED.seq_first),
    seq_last          = GREATEST(llm_job_message.seq_last, EXCLUDED.seq_last),
    created_at        = LEAST(llm_job_message.created_at, EXCLUDED.created_at)
"""
        await connection.execute(
            query_text,
            message_uuid, run_id, thread_id,
            merged_message_dictionary["message_id"],
            merged_message_dictionary["ns_path"],
            merged_message_dictionary.get("task_id"),
            merged_message_dictionary.get("parent_task_id"),
            merged_message_dictionary.get("message_metadata"),
            merged_message_dictionary.get("message_type"),
            merged_message_dictionary.get("tool_call_id"),
            merged_message_dictionary.get("agent_name"),
            bool(merged_message_dictionary.get("is_root_message")),
            merged_message_dictionary["role"],
            merged_message_dictionary["content"],
            merged_message_dictionary.get("tool_call_list"),
            merged_message_dictionary.get("usage"),
            merged_message_dictionary.get("response_metadata"),
            merged_message_dictionary["seq_first"],
            merged_message_dictionary["seq_last"],
            JobMessageRepository._get_created_at(merged_message_dictionary)
        )

    @staticmethod
    async def _get_message_count_with_connection_async(connection : asyncpg.Connection, run_id : uuid.UUID) -> int:
        message_count = await connection.fetchval("SELECT COUNT(*) FROM llm_job_message WHERE run_id = $1", run_id)
        return int(message_count)

    @staticmethod
    async def _get_last_sequence_number_with_connection_async(connection : asyncpg.Connection, run_id : uuid.UUID) -> int:
        last_sequence_number = await connection.fetchval("SELECT COALESCE(MAX(seq_last), 0) FROM llm_job_message WHERE run_id = $1", run_id)
        return int(last_sequence_number)

    @staticmethod
    async def _get_usage_dictionary_list_with_connection_async(connection : asyncpg.Connection, run_id : uuid.UUID) -> List[Dict[str, Any]]:
        record_list = await connection.fetch("SELECT usage FROM llm_job_message WHERE run_id = $1 AND usage IS NOT NULL", run_id)
        return [record["usage"] for record in record_list if isinstance(record["usage"], dict)]

    async def insert_message_async(self, message_uuid : uuid.UUID, run_id : uuid.UUID, thread_id : uuid.UUID, merged_message_dictionary : Dict[str, Any], connection : Optional[asyncpg.Connection] = None) -> None:
        if connection is not None:
            await JobMessageRepository._insert_message_with_connection_async(connection, message_uuid, run_id, thread_id, merged_message_dictionary)
            return
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            await JobMessageRepository._insert_message_with_connection_async(acquired_connection, message_uuid, run_id, thread_id, merged_message_dictionary)

    async def get_message_list_async(self, run_id : uuid.UUID) -> List[Dict[str, Any]]:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record_list = await connection.fetch("SELECT * FROM llm_job_message WHERE run_id = $1 ORDER BY seq_first ASC", run_id)
            return [JobMessageRepository._convert_record_to_dictionary(record) for record in record_list]

    async def get_message_list_after_sequence_async(self, run_id : uuid.UUID, sequence_number : int) -> List[Dict[str, Any]]:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record_list = await connection.fetch("SELECT * FROM llm_job_message WHERE run_id = $1 AND seq_last > $2 ORDER BY seq_last ASC, seq_first ASC", run_id, sequence_number)
            return [JobMessageRepository._convert_record_to_dictionary(record) for record in record_list]

    async def get_message_count_async(self, run_id : uuid.UUID, connection : Optional[asyncpg.Connection] = None) -> int:
        if connection is not None:
            return await JobMessageRepository._get_message_count_with_connection_async(connection, run_id)
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            return await JobMessageRepository._get_message_count_with_connection_async(acquired_connection, run_id)

    async def get_last_sequence_number_async(self, run_id : uuid.UUID, connection : Optional[asyncpg.Connection] = None) -> int:
        if connection is not None:
            return await JobMessageRepository._get_last_sequence_number_with_connection_async(connection, run_id)
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            return await JobMessageRepository._get_last_sequence_number_with_connection_async(acquired_connection, run_id)

    async def get_usage_dictionary_list_async(self, run_id : uuid.UUID, connection : Optional[asyncpg.Connection] = None) -> List[Dict[str, Any]]:
        if connection is not None:
            return await JobMessageRepository._get_usage_dictionary_list_with_connection_async(connection, run_id)
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            return await JobMessageRepository._get_usage_dictionary_list_with_connection_async(acquired_connection, run_id)

    async def get_last_root_ai_message_async(self, run_id : uuid.UUID) -> Optional[Dict[str, Any]]:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record = await connection.fetchrow("SELECT * FROM llm_job_message WHERE run_id = $1 AND ns_path = '' AND role = 'ai' ORDER BY seq_last DESC LIMIT 1", run_id)
            if record is None:
                return None
            return JobMessageRepository._convert_record_to_dictionary(record)

    async def get_last_assistant_message_async(self, run_id : uuid.UUID) -> Optional[Dict[str, Any]]:
        return await self.get_last_root_ai_message_async(run_id = run_id)
