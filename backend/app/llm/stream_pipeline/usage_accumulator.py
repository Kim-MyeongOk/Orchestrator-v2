from typing import Dict
from typing import Any
from typing import List
from typing import Optional

class UsageAccumulator:
    @staticmethod
    def _merge_usage_dictionary(target_dictionary : Dict[str, Any], source_dictionary : Dict[str, Any]) -> None:
        for field_name, field_value in source_dictionary.items():
            current_value = target_dictionary.get(field_name)
            if isinstance(field_value, dict):
                if not isinstance(current_value, dict):
                    current_value = {}
                    target_dictionary[field_name] = current_value
                UsageAccumulator._merge_usage_dictionary(current_value, field_value)
            elif isinstance(field_value, (int, float)) and not isinstance(field_value, bool):
                numeric_current_value = current_value if isinstance(current_value, (int, float)) else 0
                target_dictionary[field_name] = numeric_current_value + field_value
            elif current_value is None:
                target_dictionary[field_name] = field_value

    @staticmethod
    def get_usage_dictionary(usage_dictionary_list : List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        accumulated_usage_dictionary : Dict[str, Any] = {}
        for usage_dictionary in usage_dictionary_list:
            UsageAccumulator._merge_usage_dictionary(accumulated_usage_dictionary, usage_dictionary)
        return accumulated_usage_dictionary or None
