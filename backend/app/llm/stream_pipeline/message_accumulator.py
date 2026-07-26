from typing                  import Dict
from typing                  import Tuple
from typing                  import Any
from langchain_core.messages import BaseMessage
from langchain_core.messages import BaseMessageChunk
from typing                  import Optional
from typing                  import List

from app.llm.stream_pipeline.chunk_normalizer import ChunkNormalizer
from app.llm.stream_pipeline.normalized_chunk import NormalizedChunk

class MessageAccumulator:
    def __init__(self) -> None:
        self.pending_entry_dictionary       : Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.active_synthetic_id_dictionary : Dict[Tuple[str, str], str           ] = {}
        self.synthetic_id_count_dictionary  : Dict[Tuple[str, str], int           ] = {}

    @staticmethod
    def _is_stream_closed(message : BaseMessage) -> bool:
        if not isinstance(message, BaseMessageChunk):
            return True
        if ChunkNormalizer.get_message_role(message) == "tool":
            return True
        return getattr(message, "chunk_position", None) == "last"

    @staticmethod
    def _build_merged_message_dictionary(pending_entry_dictionary : Dict[str, Any]) -> Dict[str, Any]:
        message        = pending_entry_dictionary["message"]
        tool_call_list = getattr(message, "tool_calls", None) or None
        return {
            "message_id"        : pending_entry_dictionary["message_id"],
            "ns_path"           : pending_entry_dictionary["ns_path"],
            "task_id"           : pending_entry_dictionary.get("task_id"),
            "parent_task_id"    : pending_entry_dictionary.get("parent_task_id"),
            "message_metadata"  : pending_entry_dictionary.get("message_metadata"),
            "message_type"      : getattr(message, "type", type(message).__name__),
            "tool_call_id"      : getattr(message, "tool_call_id", None),
            "agent_name"        : pending_entry_dictionary.get("agent_name"),
            "is_root_message"   : pending_entry_dictionary["ns_path"] == "",
            "role"              : ChunkNormalizer.get_message_role(message),
            "content"           : ChunkNormalizer.serialize_value(getattr(message, "content", None)),
            "tool_call_list"    : ChunkNormalizer.serialize_value(tool_call_list) if tool_call_list else None,
            "usage"             : ChunkNormalizer.serialize_value(getattr(message, "usage_metadata", None) or None),
            "response_metadata" : ChunkNormalizer.serialize_value(getattr(message, "response_metadata", None) or None),
            "seq_first"         : pending_entry_dictionary["seq_first"],
            "seq_last"          : pending_entry_dictionary["seq_last"],
            "created_at"        : pending_entry_dictionary["created_at"]
        }

    def _get_message_id(self, normalized_chunk : NormalizedChunk, message : BaseMessage) -> Tuple[str, Optional[Tuple[str, str]]]:
        message_id = getattr(message, "id", None)
        if message_id:
            return str(message_id), None
        role                        = ChunkNormalizer.get_message_role(message)
        synthetic_context_key_tuple = (normalized_chunk.namespace_path, role)
        synthetic_message_id        = self.active_synthetic_id_dictionary.get(synthetic_context_key_tuple)
        if synthetic_message_id is None:
            synthetic_id_count = self.synthetic_id_count_dictionary.get(synthetic_context_key_tuple, 0) + 1
            synthetic_message_id = f"synthetic-{role}-{synthetic_id_count}"
            self.synthetic_id_count_dictionary[synthetic_context_key_tuple] = synthetic_id_count
            self.active_synthetic_id_dictionary[synthetic_context_key_tuple] = synthetic_message_id
        return synthetic_message_id, synthetic_context_key_tuple

    @staticmethod
    def _merge_message(previous_message : BaseMessage, current_message : BaseMessage) -> BaseMessage:
        if isinstance(previous_message, BaseMessageChunk) and isinstance(current_message, BaseMessageChunk):
            return previous_message + current_message
        if previous_message == current_message:
            return previous_message
        raise ValueError(f"INCOMPATIBLE MESSAGE CHUNK TYPES : {type(previous_message).__name__} + {type(current_message).__name__}")

    def accumulate(self, normalized_chunk : NormalizedChunk) -> Optional[Dict[str, Any]]:
        message = normalized_chunk.message
        if message is None:
            return None
        message_id, synthetic_context_key_tuple = self._get_message_id(normalized_chunk, message)
        merge_key                               = (f"{normalized_chunk.namespace_path}|{normalized_chunk.task_id or ''}", message_id)
        pending_entry_dictionary                = self.pending_entry_dictionary.get(merge_key)
        if pending_entry_dictionary is None:
            pending_entry_dictionary = {
                "message"          : message,
                "message_id"       : str(message_id),
                "ns_path"          : normalized_chunk.namespace_path,
                "task_id"          : normalized_chunk.task_id,
                "parent_task_id"   : normalized_chunk.parent_task_id,
                "message_metadata" : normalized_chunk.data_dictionary.get("metadata"),
                "agent_name"       : normalized_chunk.data_dictionary.get("metadata", {}).get("langgraph_node") if isinstance(normalized_chunk.data_dictionary.get("metadata"), dict) else None,
                "seq_first"        : normalized_chunk.sequence,
                "seq_last"         : normalized_chunk.sequence,
                "created_at"       : normalized_chunk.created_at
            }
            self.pending_entry_dictionary[merge_key] = pending_entry_dictionary
        else:
            pending_entry_dictionary["message"       ] = MessageAccumulator._merge_message(pending_entry_dictionary["message"], message)
            pending_entry_dictionary["seq_last"      ] = normalized_chunk.sequence
            pending_entry_dictionary["task_id"       ] = pending_entry_dictionary.get("task_id") or normalized_chunk.task_id
            pending_entry_dictionary["parent_task_id"] = pending_entry_dictionary.get("parent_task_id") or normalized_chunk.parent_task_id
        if synthetic_context_key_tuple is not None and MessageAccumulator._is_stream_closed(pending_entry_dictionary["message"]):
            self.active_synthetic_id_dictionary.pop(synthetic_context_key_tuple, None)
        # 프로세스가 즉시 종료돼도 부분 결과가 남도록 모든 청크에서 최신 누적 snapshot을 반환한다.
        return MessageAccumulator._build_merged_message_dictionary(pending_entry_dictionary)

    def flush_all(self) -> List[Dict[str, Any]]:
        # 완결 판정을 받지 못한 잔여 메시지를 seq 순으로 모두 병합 반환한다 (부분 결과 저장 경로 포함)
        pending_entry_list                  = sorted(self.pending_entry_dictionary.values(), key = lambda pending_entry_dictionary : pending_entry_dictionary["seq_first"])
        merged_message_list                 = [MessageAccumulator._build_merged_message_dictionary(pending_entry_dictionary) for pending_entry_dictionary in pending_entry_list]
        self.pending_entry_dictionary       = {}
        self.active_synthetic_id_dictionary = {}
        self.synthetic_id_count_dictionary  = {}
        return merged_message_list
