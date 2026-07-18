##################################################
# 청크 직렬화 헬퍼
# LangGraph astream(subgraphs=True, stream_mode=[...]) 이 뱉는 다양한 형태의
# 청크(2-tuple / 3-tuple)를 Redis 에 저장 가능한 JSON-safe dict 로 통일한다.
##################################################

from typing import Any
from typing import Dict
from typing import Optional
from typing import Tuple


class ChunkSerializeHelper:
    @staticmethod
    def create_json_safe_value(source_value : Any) -> Any:
        # BaseMessage / dataclass / 임의 객체를 재귀적으로 JSON 직렬화 가능한 값으로 변환한다.
        if source_value is None or isinstance(source_value, (str, int, float, bool)):
            return source_value
        if isinstance(source_value, dict):
            return {str(key) : ChunkSerializeHelper.create_json_safe_value(value) for key, value in source_value.items()}
        if isinstance(source_value, (list, tuple, set)):
            return [ChunkSerializeHelper.create_json_safe_value(item) for item in source_value]
        if hasattr(source_value, "content") and hasattr(source_value, "type"):
            # LangChain BaseMessage 계열은 핵심 필드만 추린다
            return {
                "message_id" : getattr(source_value, "id", None),
                "role"       : ChunkSerializeHelper._create_role(source_value),
                "content"    : ChunkSerializeHelper.create_json_safe_value(source_value.content)
            }
        # 직렬화 불가 객체는 문자열로 강등한다 (파이프라인이 죽지 않게 함)
        return str(source_value)

    @staticmethod
    def _create_role(message_object : Any) -> str:
        # 메시지 타입명(AIMessageChunk 등)을 표준 role(human/ai/tool/system)로 매핑한다
        type_name = str(getattr(message_object, "type", "") or message_object.__class__.__name__).lower()
        if "human" in type_name:
            return "human"
        if "tool" in type_name:
            return "tool"
        if "system" in type_name:
            return "system"
        return "ai"

    @staticmethod
    def _parse_stream_chunk(stream_chunk : Any) -> Optional[Tuple[str, str, Any]]:
        # LangGraph 1.x 는 subgraphs=True + stream_mode 리스트 조합 시 {'type', 'ns', 'data'} dict 로 청크를 보낸다.
        # 구버전 호환을 위해 (namespace_tuple, stream_mode, payload) 3-tuple / (stream_mode, payload) 2-tuple 도 함께 파싱한다.
        if isinstance(stream_chunk, dict) and "type" in stream_chunk:
            namespace_tuple = stream_chunk.get("ns") or ()
            namespace_path  = "|".join(str(namespace) for namespace in namespace_tuple)
            return namespace_path, str(stream_chunk.get("type")), stream_chunk.get("data")
        if isinstance(stream_chunk, tuple) and len(stream_chunk) == 3:
            namespace_tuple, chunk_type, payload = stream_chunk
            namespace_path = "|".join(str(namespace) for namespace in namespace_tuple)
            return namespace_path, str(chunk_type), payload
        if isinstance(stream_chunk, tuple) and len(stream_chunk) == 2:
            chunk_type, payload = stream_chunk
            return "", str(chunk_type), payload
        return None

    @staticmethod
    def create_chunk_dictionary(stream_chunk : Any) -> Optional[Dict[str, Any]]:
        parsed_tuple = ChunkSerializeHelper._parse_stream_chunk(stream_chunk)
        if parsed_tuple is None:
            return None
        namespace_path, chunk_type, payload = parsed_tuple

        if chunk_type == "messages":
            # messages 모드의 payload 는 (message_chunk, metadata_dictionary) 형태다
            message_chunk, metadata_dictionary = payload
            return {
                "chunk_type"     : "messages",
                "namespace_path" : namespace_path,
                "message_id"     : getattr(message_chunk, "id", None),
                "role"           : ChunkSerializeHelper._create_role(message_chunk),
                "content"        : ChunkSerializeHelper.create_json_safe_value(message_chunk.content),
                "metadata"       : ChunkSerializeHelper.create_json_safe_value(metadata_dictionary)
            }

        # tasks / values / custom 은 payload 를 그대로 JSON-safe 로 보존한다
        return {
            "chunk_type"     : chunk_type,
            "namespace_path" : namespace_path,
            "payload"        : ChunkSerializeHelper.create_json_safe_value(payload)
        }
