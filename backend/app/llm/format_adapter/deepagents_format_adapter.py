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

    def format_start(self) -> List[Dict[str, Any]]:
        return [DeepagentsFormatAdapter._create_projection(event_name = "__start__", data_dictionary = {"run_id" : self.run_id, "status" : "running"})]

    def format_chunk(self, normalized_chunk_dictionary : Dict[str, Any], include_events : bool) -> List[Dict[str, Any]]:
        chunk_type = str(normalized_chunk_dictionary.get("chunk_type") or "messages")
        return [DeepagentsFormatAdapter._create_projection(event_name = chunk_type, data_dictionary = normalized_chunk_dictionary)]

    def format_end(self, status : str, error_message : Optional[str], usage_dictionary : Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        end_dictionary = {
            "run_id"        : self.run_id,
            "status"        : status,
            "error_message" : error_message,
            "usage"         : usage_dictionary
        }
        return [DeepagentsFormatAdapter._create_projection(event_name = "__end__", data_dictionary = end_dictionary)]
