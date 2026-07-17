import asyncpg
import uuid

from typing   import Dict
from typing   import Any
from datetime import datetime
from datetime import timezone
from typing   import List
from typing   import Optional

from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager

class ChatThreadRepository:
    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager) -> None:
        self.postgresql_pool_manager = postgresql_pool_manager

    @staticmethod
    def _convert_record_to_dictionary(record : asyncpg.Record) -> Dict[str, Any]:
        thread_dictionary = dict(record)
        for field_name in ("thread_id", "user_id", "latest_run_id"):
            if thread_dictionary.get(field_name) is not None:
                thread_dictionary[field_name] = str(thread_dictionary[field_name])
        for field_name in ("created_at", "updated_at"):
            if thread_dictionary.get(field_name) is not None:
                thread_dictionary[field_name] = thread_dictionary[field_name].isoformat()
        return thread_dictionary

    @staticmethod
    def _get_preview(content_value : Any) -> str:
        if content_value is None:
            return ""
        if isinstance(content_value, str):
            return content_value[:200]
        return str(content_value)[:200]

    async def upsert_thread_on_submit_async(self, thread_id : uuid.UUID, user_id : uuid.UUID, run_id : uuid.UUID, message_dictionary_list : List[Dict[str, Any]], connection : Optional[asyncpg.Connection] = None) -> None:
        current_time             = datetime.now(timezone.utc)
        first_message_dictionary = message_dictionary_list[0] if message_dictionary_list else {}
        title                    = ChatThreadRepository._get_preview(first_message_dictionary.get("content")) or "새 대화"
        preview                  = title
        query_text               = """
INSERT INTO llm_thread
(
    thread_id,
    user_id,
    title,
    last_message_preview,
    latest_run_id,
    latest_status,
    created_at,
    updated_at
)
VALUES
(
    $1,
    $2,
    $3,
    $4,
    $5,
    'pending',
    $6,
    $6
)
ON CONFLICT (thread_id) DO UPDATE
SET
    last_message_preview = EXCLUDED.last_message_preview,
    latest_run_id        = EXCLUDED.latest_run_id,
    latest_status        = EXCLUDED.latest_status,
    updated_at           = EXCLUDED.updated_at
WHERE llm_thread.user_id = EXCLUDED.user_id
"""
        parameter_tuple = (thread_id, user_id, title, preview, run_id, current_time)
        if connection is not None:
            await connection.execute(query_text, *parameter_tuple)
            return
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            await acquired_connection.execute(query_text, *parameter_tuple)

    async def update_thread_on_finish_async(self, thread_id : uuid.UUID, user_id : uuid.UUID, run_id : uuid.UUID, status : str, preview : Optional[str], connection : Optional[asyncpg.Connection] = None) -> None:
        current_time = datetime.now(timezone.utc)
        query_text   = """
UPDATE llm_thread
SET
    latest_run_id        = $3,
    latest_status        = $4,
    last_message_preview = COALESCE($5, last_message_preview),
    updated_at           = $6
WHERE thread_id = $1
AND   user_id = $2
"""
        parameter_tuple = (thread_id, user_id, run_id, status, preview, current_time)
        if connection is not None:
            await connection.execute(query_text, *parameter_tuple)
            return
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            await acquired_connection.execute(query_text, *parameter_tuple)

    async def get_thread_list_async(self, user_id : uuid.UUID, cursor_updated_at : Optional[datetime], cursor_thread_id : Optional[uuid.UUID], limit_count : int) -> List[Dict[str, Any]]:
        condition_list             = ["user_id = $1"]
        parameter_list : List[Any] = [user_id]
        if cursor_updated_at is not None and cursor_thread_id is not None:
            parameter_list.append(cursor_updated_at)
            parameter_list.append(cursor_thread_id)
            condition_list.append(f"(updated_at, thread_id) < (${len(parameter_list) - 1}, ${len(parameter_list)})")
        parameter_list.append(limit_count)
        query_text = f"""
SELECT
    thread_id,
    user_id,
    title,
    last_message_preview,
    latest_run_id,
    latest_status,
    created_at,
    updated_at
FROM llm_thread
WHERE {" AND ".join(condition_list)}
ORDER BY updated_at DESC, thread_id DESC
LIMIT ${len(parameter_list)}
"""
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record_list = await connection.fetch(query_text, *parameter_list)
            return [ChatThreadRepository._convert_record_to_dictionary(record) for record in record_list]

    async def get_thread_async(self, thread_id : uuid.UUID, user_id : uuid.UUID) -> Optional[Dict[str, Any]]:
        query_text = """
SELECT
    thread_id,
    user_id,
    title,
    last_message_preview,
    latest_run_id,
    latest_status,
    created_at,
    updated_at
FROM  llm_thread
WHERE thread_id = $1
AND   user_id = $2
"""
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record = await connection.fetchrow(query_text, thread_id, user_id)
            if record is None:
                return None
            return ChatThreadRepository._convert_record_to_dictionary(record)
