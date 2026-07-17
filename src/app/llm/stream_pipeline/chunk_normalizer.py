import math
import uuid
import base64

from typing                  import Any
from datetime                import datetime
from datetime                import timezone
from langchain_core.messages import BaseMessage
from enum                    import Enum
from dataclasses             import is_dataclass
from dataclasses             import asdict
from typing                  import Dict
from typing                  import Optional
from typing                  import Tuple
from typing                  import List

from app.llm.stream_pipeline.normalized_chunk import NormalizedChunk

class ChunkNormalizer:
    # 청크 타입명(AIMessageChunk 등)을 표준 role로 정규화하는 매핑
    ROLE_MAPPING_DICTIONARY = {
        "AIMessageChunk"       : "ai",
        "HumanMessageChunk"    : "human",
        "SystemMessageChunk"   : "system",
        "ToolMessageChunk"     : "tool",
        "FunctionMessageChunk" : "function",
        "ChatMessageChunk"     : "chat",
        "ai"                   : "ai",
        "human"                : "human",
        "system"               : "system",
        "tool"                 : "tool",
        "function"             : "function",
        "chat"                 : "chat"
    }
    SUPPORTED_CHUNK_TYPE_SET = {"tasks", "messages", "custom"}

    def __init__(self) -> None:
        self._sequence_number = 0

    @staticmethod
    def get_message_role(message : Any) -> str:
        message_type = getattr(message, "type", None) or "unknown"
        return ChunkNormalizer.ROLE_MAPPING_DICTIONARY.get(message_type, message_type)

    @staticmethod
    def get_current_time_string() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def serialize_value(value : Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            if isinstance(value, float) and not math.isfinite(value):
                return str(value)
            return value
        if isinstance(value, BaseMessage):
            message_dictionary = {
                "message_id"        : getattr(value, "id", None),
                "message_type"      : getattr(value, "type", type(value).__name__),
                "role"              : ChunkNormalizer.get_message_role(value),
                "content"           : ChunkNormalizer.serialize_value(getattr(value, "content", None)),
                "name"              : getattr(value, "name", None),
                "additional_kwargs" : ChunkNormalizer.serialize_value(getattr(value, "additional_kwargs", {}))
            }
            attribute_mapping_dictionary = {
                "tool_calls"         : "tool_call_list",
                "tool_call_chunks"   : "tool_call_chunk_list",
                "invalid_tool_calls" : "invalid_tool_call_list",
                "tool_call_id"       : "tool_call_id",
                "artifact"           : "artifact",
                "status"             : "status",
                "usage_metadata"     : "usage",
                "response_metadata"  : "response_metadata",
                "chunk_position"     : "chunk_position"
            }
            for attribute_name, output_name in attribute_mapping_dictionary.items():
                if hasattr(value, attribute_name):
                    message_dictionary[output_name] = ChunkNormalizer.serialize_value(getattr(value, attribute_name))
            return message_dictionary
        if isinstance(value, dict):
            return {str(item_key) : ChunkNormalizer.serialize_value(item_value) for item_key, item_value in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [ChunkNormalizer.serialize_value(item_value) for item_value in value]
        if isinstance(value, bytes):
            return {
                "__type__"                 : "bytes",
                "__serialization_status__" : "base64",
                "encoding"                 : "base64",
                "value"                    : base64.b64encode(value).decode("ascii")
            }
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, BaseException):
            return {"error_type" : type(value).__name__, "message" : str(value)}
        if is_dataclass(value) and not isinstance(value, type):
            return ChunkNormalizer.serialize_value(asdict(value))
        if hasattr(value, "model_dump"):
            return ChunkNormalizer.serialize_value(value.model_dump(mode = "python"))
        return {
            "__type__"                 : type(value).__name__,
            "__serialization_status__" : "lossy_string",
            "value"                    : str(value)
        }

    @staticmethod
    def serialize_message(message : BaseMessage) -> Dict[str, Any]:
        serialized_message_value = ChunkNormalizer.serialize_value(message)
        if not isinstance(serialized_message_value, dict):
            raise ValueError(f"INVALID SERIALIZED MESSAGE : {type(message).__name__}")
        return serialized_message_value

    @staticmethod
    def _parse_stream_chunk(stream_chunk : Any) -> Optional[Tuple[str, Any, Any]]:
        if isinstance(stream_chunk, dict) and "type" in stream_chunk:
            return str(stream_chunk.get("type")), stream_chunk.get("ns"), stream_chunk.get("data")
        if isinstance(stream_chunk, tuple) and len(stream_chunk) == 3:
            ns_value, chunk_type, chunk_data = stream_chunk
            return str(chunk_type), ns_value, chunk_data
        if isinstance(stream_chunk, tuple) and len(stream_chunk) == 2:
            chunk_type, chunk_data = stream_chunk
            return str(chunk_type), (), chunk_data
        return None

    @staticmethod
    def _normalize_namespace_list(namespace_value : Any) -> List[str]:
        if namespace_value is None:
            return []
        if isinstance(namespace_value, str):
            return [namespace_value] if namespace_value else []
        if isinstance(namespace_value, (list, tuple, set)):
            return [str(ns_segment) for ns_segment in namespace_value]
        return [str(namespace_value)]

    @staticmethod
    def _normalize_chunk_data(chunk_type : str, chunk_data : Any) -> Tuple[Dict[str, Any], Optional[BaseMessage]]:
        if chunk_type == "messages" and isinstance(chunk_data, (tuple, list)) and len(chunk_data) == 2 and isinstance(chunk_data[0], BaseMessage):
            message = chunk_data[0]
            return {"message" : ChunkNormalizer.serialize_message(message), "metadata" : ChunkNormalizer.serialize_value(chunk_data[1])}, message
        serialized_data = ChunkNormalizer.serialize_value(chunk_data)
        if isinstance(serialized_data, dict):
            return serialized_data, None
        return {"value" : serialized_data}, None

    def get_last_sequence_number(self) -> int:
        return self._sequence_number

    def normalize(self, stream_chunk : Any) -> Optional[NormalizedChunk]:
        parsed_stream_chunk = ChunkNormalizer._parse_stream_chunk(stream_chunk)
        if parsed_stream_chunk is None:
            return None
        chunk_type, namespace_value, chunk_data = parsed_stream_chunk
        if chunk_type not in self.SUPPORTED_CHUNK_TYPE_SET:
            return None
        self._sequence_number           = self._sequence_number + 1
        namespace_list                  = ChunkNormalizer._normalize_namespace_list(namespace_value)
        namespace_path                  = "/".join(namespace_list)
        data_dictionary, message_object = ChunkNormalizer._normalize_chunk_data(chunk_type, chunk_data)
        created_at                      = ChunkNormalizer.get_current_time_string()
        return NormalizedChunk(
            sequence        = self._sequence_number,
            chunk_type      = str(chunk_type),
            namespace_list  = namespace_list,
            namespace_path  = namespace_path,
            data_dictionary = data_dictionary,
            created_at      = created_at,
            message         = message_object
        )
