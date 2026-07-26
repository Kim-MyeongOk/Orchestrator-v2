import json

from typing import Dict
from typing import Any
from typing import Optional

class SseHelper:
    @staticmethod
    def format_event(event_name : str, data_dictionary : Dict[str, Any], event_id : Optional[int] = None) -> str:
        line_list = []
        if event_id is not None:
            line_list.append(f"id: {event_id}")
        line_list.append(f"event: {event_name}")
        line_list.append(f"data: {json.dumps(data_dictionary, ensure_ascii = False, default = str)}")
        return "\n".join(line_list) + "\n\n"

    @staticmethod
    def parse_last_event_id(header_value : Optional[str]) -> Optional[int]:
        if header_value is None:
            return None
        try:
            return int(header_value.strip())
        except ValueError:
            return None
