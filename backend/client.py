import httpx
import json
import argparse
import asyncio

from typing import Optional
from typing import Type
from types  import TracebackType
from typing import Dict
from typing import AsyncIterator
from typing import Any
from typing import List

class LLMServiceClient:
    def __init__(self, base_url : str, user_id : str) -> None:
        self.base_url     = base_url.rstrip("/")
        self.user_id      = user_id
        self.async_client = httpx.AsyncClient(base_url = self.base_url, timeout = httpx.Timeout(120.0, read = None))

    async def close_async(self) -> None:
        await self.async_client.aclose()

    async def __aenter__(self) -> "LLMServiceClient":
        return self

    async def __aexit__(self, _exception_type : Optional[Type[BaseException]], _exception : Optional[BaseException], _traceback : Optional[TracebackType]) -> None:
        await self.close_async()

    def _get_header_dictionary(self, last_event_id : Optional[int] = None) -> Dict[str, str]:
        header_dictionary = {"X-User-Id" : self.user_id}
        if last_event_id is not None:
            header_dictionary["Last-Event-ID"] = str(last_event_id)
        return header_dictionary

    @staticmethod
    async def _parse_sse_async(response : httpx.Response) -> AsyncIterator[Dict[str, Any]]:
        event_name                     = "message"
        event_id       : Optional[str] = None
        data_text_list : List[str]     = []
        async for line_text in response.aiter_lines():
            if line_text == "":
                if not data_text_list:
                    continue
                data_text = "\n".join(data_text_list)
                try:
                    data_value = json.loads(data_text)
                except json.JSONDecodeError:
                    data_value = data_text
                yield {
                    "event" : event_name,
                    "id"    : event_id,
                    "data"  : data_value
                }
                event_name     = "message"
                event_id       = None
                data_text_list = []
                continue
            if line_text.startswith(":"):
                continue
            field_name, separator, field_value = line_text.partition(":")
            if not separator:
                continue
            normalized_field_value = field_value[1:] if field_value.startswith(" ") else field_value
            if field_name == "event":
                event_name = normalized_field_value
            elif field_name == "id":
                event_id = normalized_field_value
            elif field_name == "data":
                data_text_list.append(normalized_field_value)
        if data_text_list:
            data_text = "\n".join(data_text_list)
            try:
                data_value = json.loads(data_text)
            except json.JSONDecodeError:
                data_value = data_text
            yield {"event" : event_name, "id" : event_id, "data" : data_value}

    @staticmethod
    def create_argument_parser() -> argparse.ArgumentParser:
        argument_parser = argparse.ArgumentParser(description = "LLM JOB SERVICE CLIENT")
        argument_parser.add_argument("--base-url", default = "http://localhost:8000") # http://127.0.0.1:8000
        argument_parser.add_argument("--user-id", required = True)
        subparser   = argument_parser.add_subparsers(dest = "command", required = True)
        chat_parser = subparser.add_parser("chat")
        chat_parser.add_argument("message")
        chat_parser.add_argument("--thread-id")
        chat_parser.add_argument("--format", choices = ["deepagents", "openai"], default = "deepagents")
        chat_parser.add_argument("--provider")
        chat_parser.add_argument("--model-name")
        submit_parser = subparser.add_parser("submit")
        submit_parser.add_argument("message")
        submit_parser.add_argument("--thread-id")
        submit_parser.add_argument("--format", choices = ["deepagents", "openai"], default = "deepagents")
        submit_parser.add_argument("--provider")
        submit_parser.add_argument("--model-name")
        submit_parser.add_argument("--idempotency-key")
        stream_parser = subparser.add_parser("stream")
        stream_parser.add_argument("run_id")
        stream_parser.add_argument("--format", choices = ["deepagents", "openai"])
        stream_parser.add_argument("--include-events", action = "store_true")
        stream_parser.add_argument("--last-event-id", type = int)
        get_parser = subparser.add_parser("get")
        get_parser.add_argument("run_id")
        cancel_parser = subparser.add_parser("cancel")
        cancel_parser.add_argument("run_id")
        list_parser = subparser.add_parser("list")
        list_parser.add_argument("--status")
        list_parser.add_argument("--job-type", choices = ["sync", "async"])
        list_parser.add_argument("--cursor")
        list_parser.add_argument("--limit", type = int, default = 20)
        thread_list_parser = subparser.add_parser("threads")
        thread_list_parser.add_argument("--cursor")
        thread_list_parser.add_argument("--limit", type = int, default = 20)
        thread_get_parser = subparser.add_parser("thread")
        thread_get_parser.add_argument("thread_id")
        thread_get_parser.add_argument("--limit", type = int, default = 100)
        timeline_parser = subparser.add_parser("timeline")
        timeline_parser.add_argument("run_id")
        timeline_parser.add_argument("--after-seq", type = int, default = 0)
        timeline_parser.add_argument("--limit", type = int, default = 500)
        return argument_parser

    async def chat_stream_async(self, message_dictionary_list : List[Dict[str, Any]], thread_id : Optional[str] = None, output_format : str = "deepagents", model_dictionary : Optional[Dict[str, Any]] = None) -> AsyncIterator[Dict[str, Any]]:
        request_dictionary : Dict[str, Any] = {
            "messages"      : message_dictionary_list,
            "output_format" : output_format
        }
        if thread_id is not None:
            request_dictionary["thread_id"] = thread_id
        if model_dictionary is not None:
            request_dictionary["model"] = model_dictionary
        async with self.async_client.stream("POST", "/llm/chat", headers = self._get_header_dictionary(), json = request_dictionary) as response:
            response.raise_for_status()
            async for event_dictionary in LLMServiceClient._parse_sse_async(response):
                yield event_dictionary

    async def submit_job_async(self, message_dictionary_list : List[Dict[str, Any]], thread_id : Optional[str] = None, output_format : str = "deepagents", model_dictionary : Optional[Dict[str, Any]] = None, idempotency_key : Optional[str] = None) -> Dict[str, Any]:
        request_dictionary = {
            "messages"      : message_dictionary_list,
            "output_format" : output_format
        }
        if thread_id is not None:
            request_dictionary["thread_id"] = thread_id
        if model_dictionary is not None:
            request_dictionary["model"] = model_dictionary
        if idempotency_key is not None:
            request_dictionary["idempotency_key"] = idempotency_key
        response = await self.async_client.post("/llm/jobs", headers = self._get_header_dictionary(), json = request_dictionary)
        response.raise_for_status()
        return response.json()

    async def subscribe_job_async(self, run_id : str, output_format : Optional[str] = None, include_events : bool = False, last_event_id : Optional[int] = None) -> AsyncIterator[Dict[str, Any]]:
        parameter_dictionary = {"include_events" : include_events}
        if output_format is not None:
            parameter_dictionary["format"] = output_format
        async with self.async_client.stream("GET", f"/llm/jobs/{run_id}/stream", headers = self._get_header_dictionary(last_event_id), params = parameter_dictionary) as response:
            response.raise_for_status()
            async for event_dictionary in LLMServiceClient._parse_sse_async(response):
                yield event_dictionary

    async def get_job_async(self, run_id : str) -> Dict[str, Any]:
        response = await self.async_client.get(f"/llm/jobs/{run_id}", headers = self._get_header_dictionary())
        response.raise_for_status()
        return response.json()

    async def cancel_job_async(self, run_id : str) -> Dict[str, Any]:
        response = await self.async_client.delete(f"/llm/jobs/{run_id}", headers = self._get_header_dictionary())
        response.raise_for_status()
        return response.json()

    async def get_job_list_async(self, status : Optional[str] = None, job_type : Optional[str] = None, cursor : Optional[str] = None, limit_count : int = 20) -> Dict[str, Any]:
        parameter_dictionary = {"limit" : limit_count}
        for field_name, field_value in {"status" : status, "job_type" : job_type, "cursor" : cursor}.items():
            if field_value is not None:
                parameter_dictionary[field_name] = field_value
        response = await self.async_client.get("/llm/jobs", headers = self._get_header_dictionary(), params = parameter_dictionary)
        response.raise_for_status()
        return response.json()

    async def get_thread_list_async(self, cursor : Optional[str] = None, limit_count : int = 20) -> Dict[str, Any]:
        parameter_dictionary : Dict[str, Any] = {"limit" : limit_count}
        if cursor is not None:
            parameter_dictionary["cursor"] = cursor
        response = await self.async_client.get("/llm/threads", headers = self._get_header_dictionary(), params = parameter_dictionary)
        response.raise_for_status()
        return response.json()

    async def get_thread_async(self, thread_id : str, limit_count : int = 100) -> Dict[str, Any]:
        response = await self.async_client.get(f"/llm/threads/{thread_id}", headers = self._get_header_dictionary(), params = {"limit" : limit_count})
        response.raise_for_status()
        return response.json()

    async def get_job_timeline_async(self, run_id : str, after_sequence_number : int = 0, limit_count : int = 500) -> Dict[str, Any]:
        response = await self.async_client.get(f"/llm/jobs/{run_id}/timeline", headers = self._get_header_dictionary(), params = {"after_seq" : after_sequence_number, "limit" : limit_count})
        response.raise_for_status()
        return response.json()

async def main() -> None:
    argument_parser    = LLMServiceClient.create_argument_parser()
    argument_namespace = argument_parser.parse_args()
    model_dictionary   = None
    if getattr(argument_namespace, "provider", None) is not None or getattr(argument_namespace, "model_name", None) is not None:
        model_dictionary = {
            field_name : field_value
            for field_name, field_value in {
                "provider"   : getattr(argument_namespace, "provider", None),
                "model_name" : getattr(argument_namespace, "model_name", None)
            }.items()
            if field_value is not None
        }

    async with LLMServiceClient(argument_namespace.base_url, argument_namespace.user_id) as llm_service_client:
        if argument_namespace.command == "chat":
            async for event_dictionary in llm_service_client.chat_stream_async([{"role" : "user", "content" : argument_namespace.message}], argument_namespace.thread_id, argument_namespace.format, model_dictionary):
                print(json.dumps(event_dictionary, ensure_ascii = False))
        elif argument_namespace.command == "submit":
            result_dictionary = await llm_service_client.submit_job_async([{"role" : "user", "content" : argument_namespace.message}], argument_namespace.thread_id, argument_namespace.format, model_dictionary, argument_namespace.idempotency_key)
            print(json.dumps(result_dictionary, ensure_ascii = False, indent = 2))
        elif argument_namespace.command == "stream":
            async for event_dictionary in llm_service_client.subscribe_job_async(argument_namespace.run_id, argument_namespace.format, argument_namespace.include_events, argument_namespace.last_event_id):
                print(json.dumps(event_dictionary, ensure_ascii = False))
        elif argument_namespace.command == "get":
            print(json.dumps(await llm_service_client.get_job_async(argument_namespace.run_id), ensure_ascii = False, indent = 2))
        elif argument_namespace.command == "cancel":
            print(json.dumps(await llm_service_client.cancel_job_async(argument_namespace.run_id), ensure_ascii = False, indent = 2))
        elif argument_namespace.command == "list":
            result_dictionary = await llm_service_client.get_job_list_async(argument_namespace.status, argument_namespace.job_type, argument_namespace.cursor, argument_namespace.limit)
            print(json.dumps(result_dictionary, ensure_ascii = False, indent = 2))
        elif argument_namespace.command == "threads":
            result_dictionary = await llm_service_client.get_thread_list_async(argument_namespace.cursor, argument_namespace.limit)
            print(json.dumps(result_dictionary, ensure_ascii = False, indent = 2))
        elif argument_namespace.command == "thread":
            result_dictionary = await llm_service_client.get_thread_async(argument_namespace.thread_id, argument_namespace.limit)
            print(json.dumps(result_dictionary, ensure_ascii = False, indent = 2))
        elif argument_namespace.command == "timeline":
            result_dictionary = await llm_service_client.get_job_timeline_async(argument_namespace.run_id, argument_namespace.after_seq, argument_namespace.limit)
            print(json.dumps(result_dictionary, ensure_ascii = False, indent = 2))

if __name__ == "__main__":
    asyncio.run(main())
