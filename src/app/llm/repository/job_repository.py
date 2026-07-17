import asyncpg
import uuid

from typing   import Any
from typing   import Dict
from typing   import Optional
from datetime import datetime
from datetime import timezone
from typing   import List

from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager

class JobRepository:
    TERMINAL_STATUS_SET = {"completed", "failed", "cancelled"}

    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager) -> None:
        self.postgresql_pool_manager = postgresql_pool_manager

    @staticmethod
    def _convert_record_to_dictionary(record : asyncpg.Record) -> Dict[str, Any]:
        job_dictionary = dict(record)
        for field_name in ("run_id", "thread_id", "user_id", "created_user_id", "updated_user_id"):
            if job_dictionary.get(field_name) is not None:
                job_dictionary[field_name] = str(job_dictionary[field_name])
        for field_name in ("created_at", "started_at", "completed_at", "updated_at"):
            if job_dictionary.get(field_name) is not None:
                job_dictionary[field_name] = job_dictionary[field_name].isoformat()
        return job_dictionary

    @staticmethod
    async def _update_job_finished_with_connection_async(connection : asyncpg.Connection, run_id : uuid.UUID, status : str, error_message : Optional[str], usage_dictionary : Optional[Dict[str, Any]], message_count : int, event_count : int, last_sequence_number : int, chunk_count : int, task_count : int, current_time : datetime) -> bool:
        query_text = """
UPDATE llm_job
SET
    status               = $2,
    error_message        = $3,
    usage                = $4,
    message_count        = $5,
    event_count          = $6,
    last_sequence_number = $7,
    chunk_count          = $8,
    task_count           = $9,
    completed_at         = $10,
    updated_at           = $10
WHERE run_id = $1
AND   status IN ('pending', 'running')
RETURNING TRUE
"""
        is_updated = await connection.fetchval(query_text, run_id, status, error_message, usage_dictionary, message_count, event_count, last_sequence_number, chunk_count, task_count, current_time)
        return bool(is_updated)

    @staticmethod
    async def lock_job_for_chunk_async(connection : asyncpg.Connection, run_id : uuid.UUID) -> bool:
        status = await connection.fetchval("SELECT status FROM llm_job WHERE run_id = $1 FOR SHARE", run_id)
        return status in {"pending", "running"}

    @staticmethod
    async def lock_job_for_transfer_async(connection : asyncpg.Connection, run_id : uuid.UUID) -> bool:
        status = await connection.fetchval("SELECT status FROM llm_job WHERE run_id = $1 FOR UPDATE", run_id)
        return status in {"pending", "running"}

    async def insert_job_async(self, run_id : uuid.UUID, thread_id : uuid.UUID, user_id : uuid.UUID, job_type : str, status : str, output_format : str, request_payload_dictionary : Dict[str, Any], idempotency_key : Optional[str]) -> int:
        current_time = datetime.now(timezone.utc)
        query_text   = """
INSERT INTO llm_job
(
    run_id,
    thread_id,
    user_id,
    job_type,
    status,
    output_format,
    request_payload,
    turn_number,
    has_complete_chunk_history,
    idempotency_key,
    created_user_id,
    updated_user_id,
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
    $6,
    $7,
    $8,
    TRUE,
    $9,
    $10,
    $11,
    $12,
    $13
)
"""
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            async with connection.transaction():
                await connection.fetchval("SELECT pg_advisory_xact_lock(hashtextextended($1::text, 0))", str(thread_id))
                owner_user_id = await connection.fetchval("SELECT user_id FROM llm_job WHERE thread_id = $1 ORDER BY created_at ASC, run_id ASC LIMIT 1", thread_id)
                if owner_user_id is not None and owner_user_id != user_id:
                    raise ValueError(f"THREAD USER MISMATCH : {thread_id}")
                turn_number = await connection.fetchval("SELECT COALESCE(MAX(turn_number), 0) + 1 FROM llm_job WHERE thread_id = $1", thread_id)
                await connection.execute(query_text, run_id, thread_id, user_id, job_type, status, output_format, request_payload_dictionary, int(turn_number), idempotency_key, user_id, user_id, current_time, current_time)
                return int(turn_number)

    @staticmethod
    async def _insert_completed_job_with_connection_async(connection : asyncpg.Connection, run_id : uuid.UUID, thread_id : uuid.UUID, user_id : uuid.UUID, job_type : str, output_format : str, request_payload_dictionary : Dict[str, Any], final_output_dictionary : Optional[Dict[str, Any]], aggregated_event_dictionary : Optional[Dict[str, Any]], message_count : int, event_count : int, chunk_count : int, last_sequence_number : int, started_at : Optional[datetime]) -> int:
        # 오케스트레이터처럼 실행이 끝난 뒤 한 번에 저장하는 파이프라인용.
        # 종료 상태(completed)로 직접 INSERT 하므로 활성 job 부분 유니크 인덱스와 충돌하지 않으며,
        # advisory lock / 소유권 검사 / turn_number 채번은 insert_job_async 와 동일한 규칙을 따른다.
        query_text = """
INSERT INTO llm_job
(
    run_id,
    thread_id,
    user_id,
    job_type,
    status,
    output_format,
    request_payload,
    message_count,
    event_count,
    last_sequence_number,
    chunk_count,
    turn_number,
    has_complete_chunk_history,
    final_output,
    aggregated_event,
    created_user_id,
    updated_user_id,
    created_at,
    started_at,
    completed_at,
    updated_at
)
VALUES
(
    $1,
    $2,
    $3,
    $4,
    'completed',
    $5,
    $6,
    $7,
    $8,
    $9,
    $10,
    $11,
    TRUE,
    $12,
    $13,
    $14,
    $14,
    $15,
    $16,
    $17,
    $17
)
"""
        current_time = datetime.now(timezone.utc)
        await connection.fetchval("SELECT pg_advisory_xact_lock(hashtextextended($1::text, 0))", str(thread_id))
        owner_user_id = await connection.fetchval("SELECT user_id FROM llm_job WHERE thread_id = $1 ORDER BY created_at ASC, run_id ASC LIMIT 1", thread_id)
        if owner_user_id is not None and owner_user_id != user_id:
            raise ValueError(f"THREAD USER MISMATCH : {thread_id}")
        turn_number = await connection.fetchval("SELECT COALESCE(MAX(turn_number), 0) + 1 FROM llm_job WHERE thread_id = $1", thread_id)
        await connection.execute(query_text, run_id, thread_id, user_id, job_type, output_format, request_payload_dictionary, message_count, event_count, last_sequence_number, chunk_count, int(turn_number), final_output_dictionary, aggregated_event_dictionary, user_id, started_at or current_time, started_at, current_time)
        return int(turn_number)

    async def insert_completed_job_async(self, run_id : uuid.UUID, thread_id : uuid.UUID, user_id : uuid.UUID, job_type : str, output_format : str, request_payload_dictionary : Dict[str, Any], final_output_dictionary : Optional[Dict[str, Any]], aggregated_event_dictionary : Optional[Dict[str, Any]], message_count : int, event_count : int, chunk_count : int, last_sequence_number : int, started_at : Optional[datetime], connection : Optional[asyncpg.Connection] = None) -> int:
        if connection is not None:
            return await JobRepository._insert_completed_job_with_connection_async(connection, run_id, thread_id, user_id, job_type, output_format, request_payload_dictionary, final_output_dictionary, aggregated_event_dictionary, message_count, event_count, chunk_count, last_sequence_number, started_at)
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            async with acquired_connection.transaction():
                return await JobRepository._insert_completed_job_with_connection_async(acquired_connection, run_id, thread_id, user_id, job_type, output_format, request_payload_dictionary, final_output_dictionary, aggregated_event_dictionary, message_count, event_count, chunk_count, last_sequence_number, started_at)

    async def update_job_status_async(self, run_id : uuid.UUID, status : str, error_message : Optional[str] = None) -> bool:
        if status != "running" and status not in JobRepository.TERMINAL_STATUS_SET:
            raise ValueError(f"INVALID JOB STATUS TRANSITION TARGET : {status}")
        current_time = datetime.now(timezone.utc)
        query_text   = """
UPDATE llm_job
SET
    status        = $2::VARCHAR(20),
    error_message = $3,
    started_at    = CASE WHEN $2::VARCHAR(20) = 'running'::VARCHAR(20) THEN COALESCE(started_at, $4::TIMESTAMPTZ) ELSE started_at END,
    completed_at  = CASE WHEN $2::VARCHAR(20) IN ('completed'::VARCHAR(20), 'failed'::VARCHAR(20), 'cancelled'::VARCHAR(20)) THEN $4::TIMESTAMPTZ ELSE completed_at END,
    updated_at    = $4::TIMESTAMPTZ
WHERE run_id = $1
AND (($2::VARCHAR(20) = 'running'::VARCHAR(20) AND status = 'pending')
OR  ($2::VARCHAR(20) IN ('completed'::VARCHAR(20), 'failed'::VARCHAR(20), 'cancelled'::VARCHAR(20))
AND status IN ('pending', 'running')))
RETURNING TRUE
"""
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            is_updated = await connection.fetchval(query_text, run_id, status, error_message, current_time)
            return bool(is_updated)

    async def update_job_running_async(self, run_id : uuid.UUID) -> bool:
        return await self.update_job_status_async(run_id = run_id, status = "running")

    async def update_job_finished_async(self, run_id : uuid.UUID, status : str, error_message : Optional[str], usage_dictionary : Optional[Dict[str, Any]], message_count : int, event_count : int, last_sequence_number : int = 0, chunk_count : int = 0, task_count : int = 0, connection : Optional[asyncpg.Connection] = None) -> bool:
        if status not in JobRepository.TERMINAL_STATUS_SET:
            raise ValueError(f"INVALID JOB FINAL STATUS : {status}")
        current_time = datetime.now(timezone.utc)
        if connection is not None:
            return await JobRepository._update_job_finished_with_connection_async(connection, run_id, status, error_message, usage_dictionary, message_count, event_count, last_sequence_number, chunk_count, task_count, current_time)
        async with self.postgresql_pool_manager.get_pool().acquire() as acquired_connection:
            return await JobRepository._update_job_finished_with_connection_async(acquired_connection, run_id, status, error_message, usage_dictionary, message_count, event_count, last_sequence_number, chunk_count, task_count, current_time)

    async def get_job_async(self, run_id : uuid.UUID) -> Optional[Dict[str, Any]]:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record = await connection.fetchrow("SELECT * FROM llm_job WHERE run_id = $1", run_id)
            if record is None:
                return None
            return JobRepository._convert_record_to_dictionary(record)

    async def get_job_for_user_async(self, run_id : uuid.UUID, user_id : uuid.UUID) -> Optional[Dict[str, Any]]:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record = await connection.fetchrow("SELECT * FROM llm_job WHERE run_id = $1 AND user_id = $2", run_id, user_id)
            if record is None:
                return None
            return JobRepository._convert_record_to_dictionary(record)

    async def get_job_by_idempotency_key_async(self, idempotency_key : str) -> Optional[Dict[str, Any]]:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record = await connection.fetchrow("SELECT * FROM llm_job WHERE idempotency_key = $1", idempotency_key)
            if record is None:
                return None
            return JobRepository._convert_record_to_dictionary(record)

    async def get_thread_owner_user_id_async(self, thread_id : uuid.UUID) -> Optional[str]:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            owner_user_id = await connection.fetchval("SELECT user_id FROM llm_job WHERE thread_id = $1 ORDER BY created_at ASC, run_id ASC LIMIT 1", thread_id)
            return str(owner_user_id) if owner_user_id is not None else None

    async def get_thread_job_list_async(self, thread_id : uuid.UUID, user_id : Optional[uuid.UUID] = None) -> List[Dict[str, Any]]:
        # 대화 연속성 재구성을 위해 완료된 작업을 시간 오름차순으로 조회한다
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            if user_id is not None:
                record_list = await connection.fetch("SELECT * FROM llm_job WHERE thread_id = $1 AND user_id = $2 AND status = 'completed' ORDER BY created_at ASC, run_id ASC", thread_id, user_id)
                return [JobRepository._convert_record_to_dictionary(record) for record in record_list]
            record_list = await connection.fetch("SELECT * FROM llm_job WHERE thread_id = $1 AND status = 'completed' ORDER BY created_at ASC, run_id ASC", thread_id)
            return [JobRepository._convert_record_to_dictionary(record) for record in record_list]

    async def get_thread_job_list_for_user_async(self, thread_id : uuid.UUID, user_id : uuid.UUID) -> List[Dict[str, Any]]:
        return await self.get_thread_job_list_async(thread_id = thread_id, user_id = user_id)

    async def get_stale_active_job_list_async(self, stale_before : datetime) -> List[Dict[str, Any]]:
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record_list = await connection.fetch("SELECT * FROM llm_job WHERE status IN ('pending', 'running') AND updated_at < $1 ORDER BY updated_at ASC", stale_before)
            return [JobRepository._convert_record_to_dictionary(record) for record in record_list]

    async def get_job_list_async(self, user_id : uuid.UUID, status : Optional[str] = None, job_type : Optional[str] = None, cursor_created_at : Optional[datetime] = None, cursor_run_id : Optional[uuid.UUID] = None, limit_count : int = 20) -> List[Dict[str, Any]]:
        condition_list             = ["user_id = $1"]
        parameter_list : List[Any] = [user_id]
        if status is not None:
            parameter_list.append(status)
            condition_list.append(f"status = ${len(parameter_list)}")
        if job_type is not None:
            parameter_list.append(job_type)
            condition_list.append(f"job_type = ${len(parameter_list)}")
        if cursor_created_at is not None and cursor_run_id is not None:
            parameter_list.append(cursor_created_at)
            parameter_list.append(cursor_run_id)
            condition_list.append(f"(created_at, run_id) < (${len(parameter_list) - 1}, ${len(parameter_list)})")
        parameter_list.append(limit_count)
        query_text = f"""
SELECT * FROM llm_job
WHERE {" AND ".join(condition_list)}
ORDER BY created_at DESC, run_id DESC
LIMIT ${len(parameter_list)}
"""
        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            record_list = await connection.fetch(query_text, *parameter_list)
            return [JobRepository._convert_record_to_dictionary(record) for record in record_list]
