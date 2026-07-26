import uuid

from typing   import List
from typing   import Dict
from typing   import Any
from typing   import Optional
from datetime import datetime

from app.llm.repository.chat_thread_repository    import ChatThreadRepository
from app.llm.repository.thread_message_repository import ThreadMessageRepository
from app.llm.repository.job_repository            import JobRepository
from app.llm.repository.job_chunk_repository      import JobChunkRepository
from app.llm.repository.job_task_repository       import JobTaskRepository

class ChatQueryService:
    TERMINAL_STATUS_SET = {"completed", "failed", "cancelled"}

    def __init__(self, chat_thread_repository : ChatThreadRepository, thread_message_repository : ThreadMessageRepository, job_repository : JobRepository, job_chunk_repository : JobChunkRepository, job_task_repository : JobTaskRepository) -> None:
        self.chat_thread_repository    = chat_thread_repository
        self.thread_message_repository = thread_message_repository
        self.job_repository            = job_repository
        self.job_chunk_repository      = job_chunk_repository
        self.job_task_repository       = job_task_repository

    @staticmethod
    def _get_unassigned_chunk_list(chunk_dictionary_list : List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [chunk_dictionary for chunk_dictionary in chunk_dictionary_list if chunk_dictionary.get("task_link_type") == "unassigned"]

    async def get_thread_list_async(self, user_id : uuid.UUID, cursor_updated_at : Optional[datetime], cursor_thread_id : Optional[uuid.UUID], limit_count : int) -> List[Dict[str, Any]]:
        return await self.chat_thread_repository.get_thread_list_async(user_id, cursor_updated_at, cursor_thread_id, limit_count)

    async def get_thread_detail_async(self, thread_id : uuid.UUID, user_id : uuid.UUID, limit_count : int) -> Dict[str, Any]:
        thread_dictionary = await self.chat_thread_repository.get_thread_async(thread_id, user_id)
        if thread_dictionary is None:
            raise ValueError(f"THREAD NOT FOUND : {thread_id}")
        message_dictionary_list = await self.thread_message_repository.get_message_list_async(thread_id, user_id, limit_count)
        job_dictionary_list     = await self.job_repository.get_thread_job_list_async(thread_id, user_id)
        return {
            "thread"      : thread_dictionary,
            "message_list" : message_dictionary_list,
            "run_list"    : job_dictionary_list
        }

    async def get_job_timeline_async(self, run_id : uuid.UUID, user_id : uuid.UUID, after_sequence_number : int, limit_count : int) -> Dict[str, Any]:
        job_dictionary = await self.job_repository.get_job_for_user_async(run_id, user_id)
        if job_dictionary is None:
            raise ValueError(f"JOB NOT FOUND : {run_id}")
        task_dictionary_list    = await self.job_task_repository.get_task_list_async(run_id)
        chunk_dictionary_list   = await self.job_chunk_repository.get_chunk_list_after_sequence_async(run_id, after_sequence_number, limit_count)
        through_sequence_number = after_sequence_number
        if chunk_dictionary_list:
            through_sequence_number = int(chunk_dictionary_list[-1]["seq"])
        return {
            "job"                   : job_dictionary,
            "task_list"             : task_dictionary_list,
            "chunk_list"            : chunk_dictionary_list,
            "unassigned_chunk_list" : ChatQueryService._get_unassigned_chunk_list(chunk_dictionary_list),
            "through_sequence"      : through_sequence_number,
            "is_terminal"           : str(job_dictionary.get("status")) in ChatQueryService.TERMINAL_STATUS_SET,
            "next_after_sequence"   : through_sequence_number
        }
