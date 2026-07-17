import copy
import time
import json

from typing   import Optional
from typing   import Dict
from typing   import Tuple
from typing   import Any
from typing   import List
from datetime import datetime

class OpenaiResponsesFormatAdapter:
    SOURCE_SEQUENCE_MULTIPLIER = 1000

    def __init__(self, run_id : str, model_name : str = "unknown", created_at : Optional[str] = None, completed_at : Optional[str] = None) -> None:
        self.run_id                                                                      = run_id
        self.model_name                                                                  = model_name
        self._created_at_second_count                                                    = OpenaiResponsesFormatAdapter._get_timestamp_second_count(created_at)
        self._completed_at_second_count                                                  = OpenaiResponsesFormatAdapter._get_timestamp_second_count(completed_at) if completed_at is not None else None
        self._event_sequence_number                                                      = 0
        self._next_output_index                                                          = 0
        self._is_started                                                                 = False
        self._is_ended                                                                   = False
        self._message_state_dictionary      : Dict[Tuple[str, str], Dict[str, Any]]      = {}
        self._tool_state_dictionary         : Dict[Tuple[str, str, int], Dict[str, Any]] = {}
        self._output_item_state_list        : List[Dict[str, Any]]                       = []
        self._active_message_id_dictionary  : Dict[Tuple[str, str], str]                 = {}
        self._synthetic_id_count_dictionary : Dict[Tuple[str, str], int]                 = {}

    @staticmethod
    def _clone_dictionary(source_dictionary : Dict[str, Any]) -> Dict[str, Any]:
        return copy.deepcopy(source_dictionary)

    @staticmethod
    def _get_timestamp_second_count(timestamp_text : Optional[str]) -> int:
        if timestamp_text is None:
            return int(time.time())
        normalized_timestamp_text = f"{timestamp_text[:-1]}+00:00" if timestamp_text.endswith("Z") else timestamp_text
        return int(datetime.fromisoformat(normalized_timestamp_text).timestamp())

    @staticmethod
    def _extract_ns_path(normalized_chunk_dictionary : Dict[str, Any]) -> str:
        namespace_path = normalized_chunk_dictionary.get("ns_path")
        if namespace_path is not None:
            return str(namespace_path)
        namespace_list = normalized_chunk_dictionary.get("ns_list") or normalized_chunk_dictionary.get("ns") or []
        return "/".join([str(ns_segment) for ns_segment in namespace_list])

    @staticmethod
    def _extract_text(value : Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "".join([OpenaiResponsesFormatAdapter._extract_text(item_value) for item_value in value])
        if not isinstance(value, dict):
            return ""
        content_type = str(value.get("type") or "")
        if content_type in {"text", "text_delta", "output_text"}:
            text_value = value.get("text")
            if text_value is None:
                text_value = value.get("delta")
            return str(text_value or "")
        text_value = value.get("text")
        if isinstance(text_value, str):
            return text_value
        return OpenaiResponsesFormatAdapter._extract_text(value.get("content"))

    @staticmethod
    def _serialize_argument_value(argument_value : Any) -> str:
        if argument_value is None:
            return ""
        if isinstance(argument_value, str):
            return argument_value
        return json.dumps(argument_value, ensure_ascii = False, separators = (",", ":"), default = str)

    @staticmethod
    def _normalize_usage_dictionary(usage_dictionary : Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if usage_dictionary is None:
            return None
        input_token_detail_dictionary  =     usage_dictionary.get("input_tokens_details" ) or usage_dictionary.get("input_token_details" ) or {}
        output_token_detail_dictionary =     usage_dictionary.get("output_tokens_details") or usage_dictionary.get("output_token_details") or {}
        input_token_count              = int(usage_dictionary.get("input_tokens"         ) or usage_dictionary.get("prompt_tokens"       ) or 0)
        output_token_count             = int(usage_dictionary.get("output_tokens"        ) or usage_dictionary.get("completion_tokens"   ) or 0)
        total_token_count              = int(usage_dictionary.get("total_tokens"         ) or input_token_count + output_token_count)
        return {
            "input_tokens"         : input_token_count,
            "input_tokens_details" : {
                "cache_write_tokens" : int(input_token_detail_dictionary.get("cache_write_tokens") or 0),
                "cached_tokens"      : int(input_token_detail_dictionary.get("cache_read") or input_token_detail_dictionary.get("cached_tokens") or 0)
            },
            "output_tokens"         : output_token_count,
            "output_tokens_details" : {
                "reasoning_tokens" : int(output_token_detail_dictionary.get("reasoning") or output_token_detail_dictionary.get("reasoning_tokens") or 0)
            },
            "total_tokens" : total_token_count
        }

    @staticmethod
    def _is_complete_message(message_dictionary : Dict[str, Any]) -> bool:
        if str(message_dictionary.get("role") or "") == "tool":
            return True
        response_metadata_dictionary = message_dictionary.get("response_metadata") or {}
        if not isinstance(response_metadata_dictionary, dict):
            return False
        for finish_key in ("finish_reason", "stop_reason", "done"):
            if response_metadata_dictionary.get(finish_key):
                return True
        return False

    def _create_projection(self, event_name : str, event_dictionary : Dict[str, Any]) -> Dict[str, Any]:
        data_dictionary                    = OpenaiResponsesFormatAdapter._clone_dictionary(event_dictionary)
        data_dictionary["type"]           = event_name
        data_dictionary["sequence_number"] = self._event_sequence_number
        self._event_sequence_number        = self._event_sequence_number + 1
        return {
            "event_name"      : event_name,
            "data_dictionary" : data_dictionary
        }

    def _create_response_dictionary(self, status : str, error_dictionary : Optional[Dict[str, Any]], usage_dictionary : Optional[Dict[str, Any]]) -> Dict[str, Any]:
        output_item_list = [OpenaiResponsesFormatAdapter._clone_dictionary(output_item_state["item_dictionary"]) for output_item_state in self._output_item_state_list]
        return {
            "id"                     : self.run_id,
            "object"                 : "response",
            "created_at"             : self._created_at_second_count,
            "status"                 : status,
            "error"                  : error_dictionary,
            "incomplete_details"     : None,
            "instructions"           : None,
            "metadata"               : {},
            "model"                  : self.model_name,
            "output"                 : output_item_list,
            "parallel_tool_calls"    : True,
            "temperature"            : None,
            "tool_choice"            : "auto",
            "tools"                  : [],
            "top_p"                  : None,
            "background"             : False,
            "completed_at"           : self._completed_at_second_count if status in {"completed", "failed"} else None,
            "conversation"           : None,
            "max_output_tokens"      : None,
            "max_tool_calls"         : None,
            "moderation"             : None,
            "previous_response_id"   : None,
            "prompt"                 : None,
            "prompt_cache_key"       : None,
            "prompt_cache_options"   : None,
            "prompt_cache_retention" : None,
            "reasoning"              : None,
            "safety_identifier"      : None,
            "service_tier"           : None,
            "text"                   : None,
            "top_logprobs"           : None,
            "truncation"             : "disabled",
            "usage"                  : OpenaiResponsesFormatAdapter._normalize_usage_dictionary(usage_dictionary),
            "user"                   : None
        }

    def _get_message_id(self, namespace_path : str, message_dictionary : Dict[str, Any]) -> str:
        role                        = str(message_dictionary.get("role") or "unknown")
        synthetic_context_key_tuple = (namespace_path, role)
        message_id = message_dictionary.get("message_id") or message_dictionary.get("id")
        if message_id is not None:
            actual_message_id = str(message_id)
            self._active_message_id_dictionary[synthetic_context_key_tuple] = actual_message_id
            return actual_message_id
        active_message_id = self._active_message_id_dictionary.get(synthetic_context_key_tuple)
        if active_message_id is not None:
            return active_message_id
        synthetic_id_count                                               = self._synthetic_id_count_dictionary.get(synthetic_context_key_tuple, 0) + 1
        actual_message_id                                                = f"synthetic-{role}-{synthetic_id_count}"
        self._synthetic_id_count_dictionary[synthetic_context_key_tuple] = synthetic_id_count
        self._active_message_id_dictionary[synthetic_context_key_tuple]  = actual_message_id
        return actual_message_id

    def _create_message_state(self, message_key_tuple : Tuple[str, str], message_dictionary : Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        output_index            = self._next_output_index
        self._next_output_index = self._next_output_index + 1
        source_message_id       = message_key_tuple[1]
        item_id                 = source_message_id if source_message_id.startswith("msg_") else f"msg_{source_message_id}"
        item_dictionary         = {
            "id"      : item_id,
            "type"    : "message",
            "status"  : "in_progress",
            "role"    : "assistant",
            "content" : []
        }
        message_state_dictionary = {
            "message_key"     : message_key_tuple,
            "output_index"    : output_index,
            "item_dictionary" : item_dictionary,
            "text"            : "",
            "is_done"         : False
        }
        self._message_state_dictionary[message_key_tuple] = message_state_dictionary
        self._output_item_state_list.append(message_state_dictionary)
        added_projection = self._create_projection(
            event_name       = "response.output_item.added",
            event_dictionary = {
                "output_index" : output_index,
                "item"         : item_dictionary
            }
        )
        return message_state_dictionary, added_projection

    def _get_or_create_message_state(self, message_key_tuple : Tuple[str, str], message_dictionary : Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        message_state_dictionary = self._message_state_dictionary.get(message_key_tuple)
        if message_state_dictionary is not None:
            return message_state_dictionary, None
        return self._create_message_state(message_key_tuple = message_key_tuple, message_dictionary = message_dictionary)

    def _create_tool_state(self, message_key_tuple : Tuple[str, str], tool_index : int, tool_call_dictionary : Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        output_index            = self._next_output_index
        self._next_output_index = self._next_output_index + 1
        call_id                 = str(tool_call_dictionary.get("id") or tool_call_dictionary.get("call_id") or f"call_{self.run_id}_{output_index}")
        item_id                 = call_id if call_id.startswith("fc_") else f"fc_{call_id}"
        item_dictionary         = {
            "id"        : item_id,
            "type"      : "function_call",
            "status"    : "in_progress",
            "call_id"   : call_id,
            "name"      : str(tool_call_dictionary.get("name") or ""),
            "arguments" : ""
        }
        tool_state_dictionary  = {
            "message_key"     : message_key_tuple,
            "tool_index"      : tool_index,
            "output_index"    : output_index,
            "item_dictionary" : item_dictionary,
            "arguments"       : "",
            "is_done"         : False
        }
        tool_key = (message_key_tuple[0], message_key_tuple[1], tool_index)
        self._tool_state_dictionary[tool_key] = tool_state_dictionary
        self._output_item_state_list.append(tool_state_dictionary)
        added_projection = self._create_projection(
            event_name       = "response.output_item.added",
            event_dictionary = {
                "output_index" : output_index,
                "item"         : item_dictionary
            }
        )
        return tool_state_dictionary, added_projection

    def _get_or_create_tool_state(self, message_key_tuple : Tuple[str, str], tool_index : int, tool_call_dictionary : Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        tool_key              = (message_key_tuple[0], message_key_tuple[1], tool_index)
        tool_state_dictionary = self._tool_state_dictionary.get(tool_key)
        if tool_state_dictionary is None:
            return self._create_tool_state(message_key_tuple = message_key_tuple, tool_index = tool_index, tool_call_dictionary = tool_call_dictionary)
        item_dictionary = tool_state_dictionary["item_dictionary"]
        call_id         = tool_call_dictionary.get("id") or tool_call_dictionary.get("call_id")
        function_name   = tool_call_dictionary.get("name")
        if call_id:
            item_dictionary["call_id"] = str(call_id)
        if function_name:
            item_dictionary["name"] = str(function_name)
        return tool_state_dictionary, None

    def _resolve_tool_index(self, message_key_tuple : Tuple[str, str], default_tool_index : int, tool_call_dictionary : Dict[str, Any]) -> int:
        raw_tool_index = tool_call_dictionary.get("index")
        if raw_tool_index is not None:
            try:
                return int(raw_tool_index)
            except (TypeError, ValueError):
                pass
        call_id = tool_call_dictionary.get("id") or tool_call_dictionary.get("call_id")
        if call_id is not None:
            for tool_key, tool_state_dictionary in self._tool_state_dictionary.items():
                if tool_key[0] == message_key_tuple[0] and tool_key[1] == message_key_tuple[1] and tool_state_dictionary["item_dictionary"]["call_id"] == str(call_id):
                    return tool_key[2]
        return default_tool_index

    def _append_text_delta(self, message_state_dictionary : Dict[str, Any], text_delta : str) -> Optional[Dict[str, Any]]:
        if not text_delta or message_state_dictionary["is_done"]:
            return None
        message_state_dictionary["text"] = message_state_dictionary["text"] + text_delta
        return self._create_projection(
            event_name       = "response.output_text.delta",
            event_dictionary = {
                "item_id"      : message_state_dictionary["item_dictionary"]["id"],
                "output_index" : message_state_dictionary["output_index"],
                "content_index" : 0,
                "delta"        : text_delta,
                "logprobs"     : []
            }
        )

    def _append_tool_argument_delta(self, tool_state_dictionary : Dict[str, Any], argument_delta : str) -> Optional[Dict[str, Any]]:
        if not argument_delta or tool_state_dictionary["is_done"]:
            return None
        tool_state_dictionary["arguments"]                    = tool_state_dictionary["arguments"] + argument_delta
        tool_state_dictionary["item_dictionary"]["arguments"] = tool_state_dictionary["arguments"]
        return self._create_projection(
            event_name       = "response.function_call_arguments.delta",
            event_dictionary = {
                "item_id"      : tool_state_dictionary["item_dictionary"]["id"],
                "output_index" : tool_state_dictionary["output_index"],
                "delta"        : argument_delta
            }
        )

    def _complete_message_item(self, message_state_dictionary : Dict[str, Any]) -> List[Dict[str, Any]]:
        if message_state_dictionary["is_done"]:
            return []
        message_state_dictionary["is_done"        ]            = True
        message_state_dictionary["item_dictionary"]["status" ] = "completed"
        message_state_dictionary["item_dictionary"]["content"] = [
            {
                "type"        : "output_text",
                "text"        : message_state_dictionary["text"],
                "annotations" : [],
                "logprobs"    : []
            }
        ]
        text_done_projection = self._create_projection(
            event_name       = "response.output_text.done",
            event_dictionary = {
                "item_id"       : message_state_dictionary["item_dictionary"]["id"],
                "output_index"  : message_state_dictionary["output_index"],
                "content_index" : 0,
                "text"          : message_state_dictionary["text"],
                "logprobs"      : []
            }
        )
        item_done_projection = self._create_projection(
            event_name       = "response.output_item.done",
            event_dictionary = {
                "output_index" : message_state_dictionary["output_index"],
                "item"         : message_state_dictionary["item_dictionary"]
            }
        )
        return [text_done_projection, item_done_projection]

    def _complete_tool_item(self, tool_state_dictionary : Dict[str, Any]) -> List[Dict[str, Any]]:
        if tool_state_dictionary["is_done"]:
            return []
        tool_state_dictionary["is_done"        ]              = True
        tool_state_dictionary["item_dictionary"]["status"]    = "completed"
        tool_state_dictionary["item_dictionary"]["arguments"] = tool_state_dictionary["arguments"]
        argument_done_projection                              = self._create_projection(
            event_name       = "response.function_call_arguments.done",
            event_dictionary = {
                "item_id"      : tool_state_dictionary["item_dictionary"]["id"],
                "output_index" : tool_state_dictionary["output_index"],
                "name"         : tool_state_dictionary["item_dictionary"]["name"],
                "arguments"    : tool_state_dictionary["arguments"]
            }
        )
        item_done_projection = self._create_projection(
            event_name       = "response.output_item.done",
            event_dictionary = {
                "output_index" : tool_state_dictionary["output_index"],
                "item"         : tool_state_dictionary["item_dictionary"]
            }
        )
        return [argument_done_projection, item_done_projection]

    def _complete_message(self, message_key_tuple : Tuple[str, str]) -> List[Dict[str, Any]]:
        projection_list          = []
        message_state_dictionary = self._message_state_dictionary.get(message_key_tuple)
        if message_state_dictionary is not None:
            projection_list.extend(self._complete_message_item(message_state_dictionary))
        tool_state_list = [tool_state_dictionary for tool_key, tool_state_dictionary in self._tool_state_dictionary.items() if tool_key[0] == message_key_tuple[0] and tool_key[1] == message_key_tuple[1]]
        tool_state_list.sort(key = lambda tool_state_dictionary : tool_state_dictionary["output_index"])
        for tool_state_dictionary in tool_state_list:
            projection_list.extend(self._complete_tool_item(tool_state_dictionary))
        active_context_key_list = [context_key_tuple for context_key_tuple, active_message_id in self._active_message_id_dictionary.items() if context_key_tuple[0] == message_key_tuple[0] and active_message_id == message_key_tuple[1]]
        for active_context_key_tuple in active_context_key_list:
            del self._active_message_id_dictionary[active_context_key_tuple]
        return projection_list

    def _complete_all_items(self) -> List[Dict[str, Any]]:
        projection_list  = []
        message_key_set  = set()
        message_key_list = []
        for output_item_state in self._output_item_state_list:
            message_key_tuple = output_item_state["message_key"]
            if message_key_tuple in message_key_set:
                continue
            message_key_set.add(message_key_tuple)
            message_key_list.append(message_key_tuple)
        for message_key_tuple in message_key_list:
            projection_list.extend(self._complete_message(message_key_tuple))
        return projection_list

    def _format_tool_call_list(self, message_key_tuple : Tuple[str, str], tool_call_list : List[Dict[str, Any]], is_merged : bool) -> List[Dict[str, Any]]:
        projection_list = []
        for default_tool_index, tool_call_dictionary in enumerate(tool_call_list):
            if not isinstance(tool_call_dictionary, dict):
                continue
            tool_index = self._resolve_tool_index(message_key_tuple = message_key_tuple, default_tool_index = default_tool_index, tool_call_dictionary = tool_call_dictionary)
            tool_state_dictionary, added_projection = self._get_or_create_tool_state(message_key_tuple = message_key_tuple, tool_index = tool_index, tool_call_dictionary = tool_call_dictionary)
            if added_projection is not None:
                projection_list.append(added_projection)
            argument_value = tool_call_dictionary.get("args")
            if argument_value is None:
                argument_value = tool_call_dictionary.get("arguments")
            full_argument_text = OpenaiResponsesFormatAdapter._serialize_argument_value(argument_value)
            if is_merged:
                current_argument_text = tool_state_dictionary["arguments"]
                if full_argument_text.startswith(current_argument_text):
                    argument_delta = full_argument_text[len(current_argument_text):]
                elif current_argument_text == full_argument_text:
                    argument_delta = ""
                else:
                    argument_delta = full_argument_text
                delta_projection = self._append_tool_argument_delta(tool_state_dictionary = tool_state_dictionary, argument_delta = argument_delta)
                if delta_projection is not None:
                    projection_list.append(delta_projection)
                continue
            current_argument_text = tool_state_dictionary["arguments"]
            if current_argument_text and full_argument_text.startswith(current_argument_text):
                argument_delta = full_argument_text[len(current_argument_text):]
            elif current_argument_text == full_argument_text:
                argument_delta = ""
            else:
                argument_delta = full_argument_text
            delta_projection = self._append_tool_argument_delta(tool_state_dictionary = tool_state_dictionary, argument_delta = argument_delta)
            if delta_projection is not None:
                projection_list.append(delta_projection)
        return projection_list

    def _prepare_message(self, namespace_path : str, message_dictionary : Dict[str, Any]) -> Tuple[Tuple[str, str], List[Dict[str, Any]]]:
        projection_list          = []
        message_id               = self._get_message_id(namespace_path = namespace_path, message_dictionary = message_dictionary)
        message_key_tuple        = (namespace_path, message_id)
        text_value               = OpenaiResponsesFormatAdapter._extract_text(message_dictionary.get("content"))
        tool_call_chunk_list     = message_dictionary.get("tool_call_chunk_list") or []
        tool_call_list           = message_dictionary.get("tool_call_list") or []
        has_tool_call            = bool(tool_call_chunk_list or tool_call_list)
        message_state_dictionary = self._message_state_dictionary.get(message_key_tuple)
        if message_state_dictionary is not None or text_value or not has_tool_call:
            _message_state_dictionary, added_projection = self._get_or_create_message_state(message_key_tuple = message_key_tuple, message_dictionary = message_dictionary)
            if added_projection is not None:
                projection_list.append(added_projection)
        actual_tool_call_list = tool_call_chunk_list if isinstance(tool_call_chunk_list, list) and tool_call_chunk_list else tool_call_list
        if isinstance(actual_tool_call_list, list):
            for default_tool_index, tool_call_dictionary in enumerate(actual_tool_call_list):
                if not isinstance(tool_call_dictionary, dict):
                    continue
                tool_index                               = self._resolve_tool_index(message_key_tuple = message_key_tuple, default_tool_index = default_tool_index, tool_call_dictionary = tool_call_dictionary)
                _tool_state_dictionary, added_projection = self._get_or_create_tool_state(message_key_tuple = message_key_tuple, tool_index = tool_index, tool_call_dictionary = tool_call_dictionary)
                if added_projection is not None:
                    projection_list.append(added_projection)
        return message_key_tuple, projection_list

    def _format_message(self, ns_path : str, message_dictionary : Dict[str, Any], is_merged : bool) -> List[Dict[str, Any]]:
        message_key_tuple, projection_list = self._prepare_message(namespace_path = ns_path, message_dictionary = message_dictionary)
        text_value                         = OpenaiResponsesFormatAdapter._extract_text(message_dictionary.get("content"))
        tool_call_chunk_list               = message_dictionary.get("tool_call_chunk_list") or []
        tool_call_list                     = message_dictionary.get("tool_call_list"      ) or []
        is_complete_message                = OpenaiResponsesFormatAdapter._is_complete_message(message_dictionary)
        message_state_dictionary           = self._message_state_dictionary.get(message_key_tuple)
        if message_state_dictionary is not None:
            text_delta = text_value
            if is_merged:
                current_text = message_state_dictionary["text"]
                if text_value.startswith(current_text):
                    text_delta = text_value[len(current_text):]
                elif current_text == text_value:
                    text_delta = ""
            text_delta_projection = self._append_text_delta(message_state_dictionary = message_state_dictionary, text_delta = text_delta)
            if text_delta_projection is not None:
                projection_list.append(text_delta_projection)
        if isinstance(tool_call_chunk_list, list) and tool_call_chunk_list:
            projection_list.extend(self._format_tool_call_list(message_key_tuple = message_key_tuple, tool_call_list = tool_call_chunk_list, is_merged = is_merged))
        elif isinstance(tool_call_list, list) and tool_call_list:
            projection_list.extend(self._format_tool_call_list(message_key_tuple = message_key_tuple, tool_call_list = tool_call_list, is_merged = is_merged))
        if is_complete_message:
            projection_list.extend(self._complete_message(message_key_tuple))
        return projection_list

    def set_completed_at(self, completed_at : Optional[str]) -> None:
        if completed_at is not None:
            self._completed_at_second_count = OpenaiResponsesFormatAdapter._get_timestamp_second_count(completed_at)

    def set_source_sequence_number(self, source_sequence_number : int) -> None:
        minimum_event_sequence_number = source_sequence_number * OpenaiResponsesFormatAdapter.SOURCE_SEQUENCE_MULTIPLIER
        self._event_sequence_number = max(self._event_sequence_number, minimum_event_sequence_number)

    def format_start(self) -> List[Dict[str, Any]]:
        if self._is_started:
            return []
        self._is_started = True
        created_projection = self._create_projection(
            event_name       = "response.created",
            event_dictionary = {"response" : self._create_response_dictionary(status = "in_progress", error_dictionary = None, usage_dictionary = None)}
        )
        in_progress_projection = self._create_projection(
            event_name       = "response.in_progress",
            event_dictionary = {"response" : self._create_response_dictionary(status = "in_progress", error_dictionary = None, usage_dictionary = None)}
        )
        return [created_projection, in_progress_projection]

    def format_chunk(self, normalized_chunk_dictionary : Dict[str, Any], include_events : bool) -> List[Dict[str, Any]]:
        if self._is_ended:
            return []
        projection_list        = self.format_start()
        source_sequence_number = int(normalized_chunk_dictionary.get("seq") or 0)
        self.set_source_sequence_number(source_sequence_number)
        chunk_type = str(normalized_chunk_dictionary.get("chunk_type") or "")
        if chunk_type in {"tasks", "custom"}:
            if include_events:
                projection_list.append(self._create_projection(event_name = chunk_type, event_dictionary = normalized_chunk_dictionary))
            return projection_list
        if chunk_type != "messages":
            return projection_list
        data_dictionary    = normalized_chunk_dictionary.get("data_dictionary") or {}
        message_dictionary = data_dictionary.get("message") if isinstance(data_dictionary, dict) else None
        if not isinstance(message_dictionary, dict):
            return projection_list
        namespace_path = OpenaiResponsesFormatAdapter._extract_ns_path(normalized_chunk_dictionary)
        projection_list.extend(self._format_message(ns_path = namespace_path, message_dictionary = message_dictionary, is_merged = False))
        return projection_list

    def format_merged_message(self, message_dictionary : Dict[str, Any]) -> List[Dict[str, Any]]:
        if self._is_ended:
            return []
        projection_list        = self.format_start()
        source_sequence_number = int(message_dictionary.get("seq_last") or 0)
        self.set_source_sequence_number(source_sequence_number)
        ns_path                = str(message_dictionary.get("ns_path") or "")
        projection_list.extend(self._format_message(ns_path = ns_path, message_dictionary = message_dictionary, is_merged = True))
        return projection_list

    def format_merged_message_added(self, message_dictionary : Dict[str, Any]) -> List[Dict[str, Any]]:
        if self._is_ended:
            return []
        projection_list        = self.format_start()
        source_sequence_number = int(message_dictionary.get("seq_first") or 0)
        self.set_source_sequence_number(source_sequence_number)
        ns_path                = str(message_dictionary.get("ns_path") or "")
        _message_key_tuple, added_projection_list = self._prepare_message(namespace_path = ns_path, message_dictionary = message_dictionary)
        projection_list.extend(added_projection_list)
        return projection_list

    def format_end(self, status : str, error_message : Optional[str], usage_dictionary : Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self._is_ended:
            return []
        projection_list = self.format_start()
        projection_list.extend(self._complete_all_items())
        self._is_ended = True
        if self._completed_at_second_count is None:
            self._completed_at_second_count = int(time.time())
        normalized_status = status.lower()
        if normalized_status == "completed":
            completed_response_dictionary = self._create_response_dictionary(status = "completed", error_dictionary = None, usage_dictionary = usage_dictionary)
            projection_list.append(self._create_projection(event_name = "response.completed", event_dictionary = {"response" : completed_response_dictionary}))
            return projection_list
        error_dictionary = {
            "code"    : "server_error",
            "message" : error_message or normalized_status.upper()
        }
        failed_response_dictionary = self._create_response_dictionary(status = "failed", error_dictionary = error_dictionary, usage_dictionary = usage_dictionary)
        projection_list.append(self._create_projection(event_name = "response.failed", event_dictionary = {"response" : failed_response_dictionary}))
        return projection_list
