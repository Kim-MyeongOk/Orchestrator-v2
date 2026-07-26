from typing import Dict
from typing import Any
from typing import Optional

from app.llm.stream_pipeline.normalized_chunk import NormalizedChunk

class TaskProjector:
    @staticmethod
    def _get_task_status(data_dictionary : Dict[str, Any]) -> str:
        if data_dictionary.get("interrupts"):
            return "interrupted"
        if data_dictionary.get("error"):
            return "failed"
        if "result" in data_dictionary:
            return "completed"
        return "running"

    @staticmethod
    def _get_error_message(data_dictionary : Dict[str, Any]) -> Optional[str]:
        error_value = data_dictionary.get("error")
        if error_value is None:
            return None
        if isinstance(error_value, dict):
            message_value = error_value.get("message")
            return str(message_value) if message_value is not None else str(error_value)
        return str(error_value)

    @staticmethod
    def create_task_projection_dictionary(normalized_chunk : NormalizedChunk) -> Optional[Dict[str, Any]]:
        if normalized_chunk.chunk_type != "tasks" or normalized_chunk.task_id is None:
            return None
        data_dictionary = normalized_chunk.data_dictionary
        status          = TaskProjector._get_task_status(data_dictionary)
        return {
            "task_id"            : normalized_chunk.task_id,
            "parent_task_id"     : normalized_chunk.parent_task_id,
            "task_name"          : data_dictionary.get("name"),
            "agent_name"         : data_dictionary.get("agent_name"),
            "status"             : status,
            "input"              : data_dictionary.get("input"),
            "result"             : data_dictionary.get("result"),
            "error_message"      : TaskProjector._get_error_message(data_dictionary),
            "interrupt_list"     : data_dictionary.get("interrupts"),
            "trigger_list"       : data_dictionary.get("triggers"),
            "metadata"           : data_dictionary.get("metadata"),
            "sequence_number"    : normalized_chunk.sequence,
            "created_at"         : normalized_chunk.created_at,
            "is_status_inferred" : False,
            "is_terminal_status" : status in {"completed", "failed", "interrupted"}
        }
