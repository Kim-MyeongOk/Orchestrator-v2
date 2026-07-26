import asyncpg
import uuid

from typing   import Dict
from typing   import Any
from datetime import datetime
from datetime import timezone
from typing   import List
from typing   import Optional

from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager

class JobTaskRepository:
    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager) -> None:
        self.postgresql_pool_manager = postgresql_pool_manager

    @staticmethod
    def _convert_record_to_dictionary(record : asyncpg.Record) -> Dict[str, Any]:
        task_dictionary = dict(record)
        if task_dictionary.get("run_id") is not None:
            task_dictionary["run_id"] = str(task_dictionary["run_id"])
        for field_name in ("started_at", "completed_at", "updated_at"):
            if task_dictionary.get(field_name) is not None:
                task_dictionary[field_name] = task_dictionary[field_name].isoformat()
        return task_dictionary

    @staticmethod
    def _get_datetime(created_at_text : str) -> datetime:
        normalized_text = f"{created_at_text[:-1]}+00:00" if created_at_text.endswith("Z") else created_at_text
        try:
            created_at = datetime.fromisoformat(normalized_text)
        except ValueError as exception:
            raise ValueError(f"INVALID TASK CREATED AT : {created_at_text}") from exception
        return created_at.replace(tzinfo = timezone.utc) if created_at.tzinfo is None else created_at.astimezone(timezone.utc)

    @staticmethod
    async def _upsert_task_with_connection_async(connection : asyncpg.Connection, run_id : uuid.UUID, task_projection_dictionary : Dict[str, Any]) -> None:
        event_time = JobTaskRepository._get_datetime(str(task_projection_dictionary["created_at"]))
        query_text = """
INSERT INTO llm_job_task
(
    run_id,
    task_id,
    parent_task_id,
    task_name,
    agent_name,
    status,
    input,
    result,
    error_message,
    interrupt_list,
    trigger_list,
    metadata,
    started_sequence_number,
    completed_sequence_number,
    started_at,
    completed_at,
    updated_at,
    is_status_inferred
)
VALUES
(
    $1,
    $2,
    $3,
    $4,
    $5,
    $6::VARCHAR(30),
    $7,
    $8,
    $9,
    $10,
    $11,
    $12,
    CASE WHEN $6::VARCHAR(30) =  'running'::VARCHAR(30) THEN $13::INTEGER     ELSE NULL::INTEGER     END,
    CASE WHEN $6::VARCHAR(30) <> 'running'::VARCHAR(30) THEN $13::INTEGER     ELSE NULL::INTEGER     END,
    CASE WHEN $6::VARCHAR(30) =  'running'::VARCHAR(30) THEN $14::TIMESTAMPTZ ELSE NULL::TIMESTAMPTZ END,
    CASE WHEN $6::VARCHAR(30) <> 'running'::VARCHAR(30) THEN $14::TIMESTAMPTZ ELSE NULL::TIMESTAMPTZ END,
    $14::TIMESTAMPTZ,
    $15
)
ON CONFLICT (run_id, task_id) DO UPDATE
SET
    parent_task_id            = COALESCE(EXCLUDED.parent_task_id             , llm_job_task.parent_task_id           ),
    task_name                 = COALESCE(EXCLUDED.task_name                  , llm_job_task.task_name                ),
    agent_name                = COALESCE(EXCLUDED.agent_name                 , llm_job_task.agent_name               ),
    status                    = EXCLUDED.status,
    input                     = COALESCE(EXCLUDED.input                      , llm_job_task.input                    ),
    result                    = COALESCE(EXCLUDED.result                     , llm_job_task.result                   ),
    error_message             = COALESCE(EXCLUDED.error_message              , llm_job_task.error_message            ),
    interrupt_list            = COALESCE(EXCLUDED.interrupt_list             , llm_job_task.interrupt_list           ),
    trigger_list              = COALESCE(EXCLUDED.trigger_list               , llm_job_task.trigger_list             ),
    metadata                  = COALESCE(EXCLUDED.metadata                   , llm_job_task.metadata                 ),
    started_sequence_number   = COALESCE(llm_job_task.started_sequence_number, EXCLUDED.started_sequence_number      ),
    completed_sequence_number = COALESCE(EXCLUDED.completed_sequence_number  , llm_job_task.completed_sequence_number),
    started_at                = COALESCE(llm_job_task.started_at             , EXCLUDED.started_at                   ),
    completed_at              = COALESCE(EXCLUDED.completed_at               , llm_job_task.completed_at             ),
    updated_at                = EXCLUDED.updated_at,
    is_status_inferred = EXCLUDED.is_status_inferred
"""
        await connection.execute(
            query_text,
            run_id,
            task_projection_dictionary["task_id"],
            task_projection_dictionary.get("parent_task_id"),
            task_projection_dictionary.get("task_name"),
            task_projection_dictionary.get("agent_name"),
            task_projection_dictionary["status"],
            task_projection_dictionary.get("input"),
            task_projection_dictionary.get("result"),
            task_projection_dictionary.get("error_message"),
            task_projection_dictionary.get("interrupt_list"),
            task_projection_dictionary.get("trigger_list"),
            task_projection_dictionary.get("metadata"),
            task_projection_dictionary["sequence_number"],
            event_time,
            bool(task_projection_dictionary.get("is_status_inferred"))
        )

    async def upsert_task_async(self, run_id : uuid.UUID, task_projection_dictionary : Dict[str, Any], connection : Optional[asyncpg.Connection] = None) -> None:
        if connection is not None:
            await JobTaskRepository._upsert_task_with_connection_async(connection, run_id, task_projection_dictionary)
            return
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            await JobTaskRepository._upsert_task_with_connection_async(acquired_connection, run_id, task_projection_dictionary)

    async def mark_unfinished_task_list_async(self, run_id : uuid.UUID, terminal_status : str, connection : Optional[asyncpg.Connection] = None) -> None:
        final_status = "cancelled" if terminal_status == "cancelled" else "incomplete"
        query_text = """
UPDATE llm_job_task
SET
    status             = $2,
    completed_at       = COALESCE(completed_at, NOW()),
    updated_at         = NOW(),
    is_status_inferred = TRUE
WHERE run_id = $1
AND   status = 'running'
"""
        if connection is not None:
            await connection.execute(query_text, run_id, final_status)
            return
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            await acquired_connection.execute(query_text, run_id, final_status)

    async def get_task_list_async(self, run_id : uuid.UUID) -> List[Dict[str, Any]]:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record_list = await connection.fetch("SELECT * FROM llm_job_task WHERE run_id = $1 ORDER BY COALESCE(started_sequence_number, completed_sequence_number), task_id", run_id)
            return [JobTaskRepository._convert_record_to_dictionary(record) for record in record_list]

    async def get_task_count_async(self, run_id : uuid.UUID, connection : Optional[asyncpg.Connection] = None) -> int:
        query_text = "SELECT COUNT(*) FROM llm_job_task WHERE run_id = $1"
        if connection is not None:
            task_count = await connection.fetchval(query_text, run_id)
            return int(task_count)
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            task_count = await acquired_connection.fetchval(query_text, run_id)
            return int(task_count)
