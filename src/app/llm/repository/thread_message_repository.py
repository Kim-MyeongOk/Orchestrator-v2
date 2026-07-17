import asyncpg
import uuid

from typing   import Dict
from typing   import Any
from datetime import datetime
from datetime import timezone
from typing   import List
from typing   import Optional

from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager

class ThreadMessageRepository:
    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager) -> None:
        self.postgresql_pool_manager = postgresql_pool_manager

    @staticmethod
    def _convert_record_to_dictionary(record : asyncpg.Record) -> Dict[str, Any]:
        message_dictionary = dict(record)
        for field_name in ("id", "thread_id", "run_id"):
            if message_dictionary.get(field_name) is not None:
                message_dictionary[field_name] = str(message_dictionary[field_name])
        if message_dictionary.get("created_at") is not None:
            message_dictionary["created_at"] = message_dictionary["created_at"].isoformat()
        return message_dictionary

    @staticmethod
    def _get_content_text(content_value : Any) -> str:
        if content_value is None:
            return ""
        if isinstance(content_value, str):
            return content_value
        return str(content_value)

    async def insert_user_message_list_async(self, uuid_v7_generator : Any, thread_id : uuid.UUID, run_id : uuid.UUID, turn_number : int, message_dictionary_list : List[Dict[str, Any]], connection : Optional[asyncpg.Connection] = None) -> None:
        current_time = datetime.now(timezone.utc)
        query_text   = """
INSERT INTO llm_thread_message
(
    id,
    thread_id,
    run_id,
    turn_number,
    message_order,
    role,
    content,
    source_message_id,
    source_task_id,
    is_display_message,
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
    NULL,
    NULL,
    TRUE,
    $8
)
ON CONFLICT (run_id, message_order, role) DO NOTHING
"""
        async def execute_async(target_connection : asyncpg.Connection) -> None:
            message_order = 0
            for message_dictionary in message_dictionary_list:
                if message_dictionary.get("role") != "user":
                    continue
                message_order = message_order + 1
                await target_connection.execute(
                    query_text,
                    uuid_v7_generator.generate(),
                    thread_id,
                    run_id,
                    turn_number,
                    message_order,
                    "user",
                    ThreadMessageRepository._get_content_text(message_dictionary.get("content")),
                    current_time
                )
        if connection is not None:
            await execute_async(connection)
            return
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            await execute_async(acquired_connection)

    async def upsert_assistant_message_async(self, message_uuid : uuid.UUID, thread_id : uuid.UUID, run_id : uuid.UUID, turn_number : int, message_order : int, merged_message_dictionary : Dict[str, Any], connection : Optional[asyncpg.Connection] = None) -> None:
        query_text      = """
INSERT INTO llm_thread_message
(
    id,
    thread_id,
    run_id,
    turn_number,
    message_order,
    role,
    content,
    source_message_id,
    source_task_id,
    is_display_message,
    created_at
)
VALUES
(
    $1,
    $2,
    $3,
    $4,
    $5,
    'assistant',
    $6,
    $7,
    $8,
    TRUE,
    NOW()
)
ON CONFLICT (run_id, message_order, role) DO UPDATE
SET
    content           = EXCLUDED.content,
    source_message_id = EXCLUDED.source_message_id,
    source_task_id    = EXCLUDED.source_task_id,
    created_at        = EXCLUDED.created_at
"""
        parameter_tuple = (
            message_uuid,
            thread_id,
            run_id,
            turn_number,
            message_order,
            ThreadMessageRepository._get_content_text(merged_message_dictionary.get("content")),
            merged_message_dictionary.get("message_id"),
            merged_message_dictionary.get("task_id")
        )
        if connection is not None:
            await connection.execute(query_text, *parameter_tuple)
            return
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            await acquired_connection.execute(query_text, *parameter_tuple)

    async def get_message_list_async(self, thread_id : uuid.UUID, user_id : uuid.UUID, limit_count : int) -> List[Dict[str, Any]]:
        query_text = """
SELECT message.*
FROM   llm_thread_message message
JOIN   llm_thread         thread  ON thread.thread_id = message.thread_id
WHERE message.thread_id          = $1
AND   thread.user_id             = $2
AND   message.is_display_message = TRUE
ORDER BY
    message.turn_number   ASC,
    message.message_order ASC,
    message.created_at    ASC
LIMIT $3
"""
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record_list = await connection.fetch(query_text, thread_id, user_id, limit_count)
            return [ThreadMessageRepository._convert_record_to_dictionary(record) for record in record_list]
