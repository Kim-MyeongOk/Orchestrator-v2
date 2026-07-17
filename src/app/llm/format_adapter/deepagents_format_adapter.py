from typing import Dict
from typing import Any
from typing import List
from typing import Optional

class DeepagentsFormatAdapter:
    def __init__(self, run_id : str) -> None:
        self.run_id = run_id

    @staticmethod
    def _create_projection(event_name : str, data_dictionary : Dict[str, Any]) -> Dict[str, Any]:
        return {
            "event_name"      : event_name,
            "data_dictionary" : data_dictionary
        }

    @staticmethod
    def _create_merged_message_envelope(message_dictionary : Dict[str, Any]) -> Dict[str, Any]:
        namespace_path                = str(message_dictionary.get("ns_path") or "")
        namespace_list                = namespace_path.split("/") if namespace_path else []
        normalized_message_dictionary = {
            "message_id" : message_dictionary.get("message_id"),
            "role"       : message_dictionary.get("role"),
            "content"    : message_dictionary.get("content")
        }
        for field_name in ("tool_call_list", "usage", "response_metadata"):
            field_value = message_dictionary.get(field_name)
            if field_value is not None:
                normalized_message_dictionary[field_name] = field_value
        return {
            "seq"             : message_dictionary.get("seq_last"),
            "chunk_type"      : "messages",
            "ns_list"         : namespace_list,
            "ns_path"         : namespace_path,
            "data_dictionary" : {
                "message"  : normalized_message_dictionary,
                "metadata" : {
                    "is_merged" : True,
                    "seq_first" : message_dictionary.get("seq_first"),
                    "seq_last"  : message_dictionary.get("seq_last")
                }
            },
            "created_at"      : message_dictionary.get("created_at")
        }

    def format_start(self) -> List[Dict[str, Any]]:
        return [DeepagentsFormatAdapter._create_projection(event_name = "__start__", data_dictionary = {"run_id" : self.run_id, "status" : "running"})]

    def format_chunk(self, normalized_chunk_dictionary : Dict[str, Any], include_events : bool) -> List[Dict[str, Any]]:
        chunk_type = str(normalized_chunk_dictionary.get("chunk_type") or "messages")
        return [DeepagentsFormatAdapter._create_projection(event_name = chunk_type, data_dictionary = normalized_chunk_dictionary)]

    def format_merged_message(self, message_dictionary : Dict[str, Any]) -> List[Dict[str, Any]]:
        merged_message_envelope = DeepagentsFormatAdapter._create_merged_message_envelope(message_dictionary)
        return [DeepagentsFormatAdapter._create_projection(event_name = "messages", data_dictionary = merged_message_envelope)]

    def format_end(self, status : str, error_message : Optional[str], usage_dictionary : Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        end_dictionary = {
            "run_id"        : self.run_id,
            "status"        : status,
            "error_message" : error_message,
            "usage"         : usage_dictionary
        }
        return [DeepagentsFormatAdapter._create_projection(event_name = "__end__", data_dictionary = end_dictionary)]
