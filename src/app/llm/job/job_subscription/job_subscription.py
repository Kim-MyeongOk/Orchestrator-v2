import uuid
import json
import asyncio

from typing           import Optional
from typing           import Union
from typing           import List
from typing           import Dict
from typing           import Any
from typing           import AsyncIterator
from redis.exceptions import RedisError

from common.cache.redis_stream.redis_stream_client          import RedisStreamClient
from app.llm.job.job_configuration                          import JobConfiguration
from app.llm.repository.job_repository                      import JobRepository
from app.llm.repository.job_message_repository              import JobMessageRepository
from app.llm.repository.job_event_repository                import JobEventRepository
from app.llm.repository.job_chunk_repository                import JobChunkRepository
from app.llm.format_adapter.deepagents_format_adapter       import DeepagentsFormatAdapter
from app.llm.format_adapter.openai_responses_format_adapter import OpenaiResponsesFormatAdapter
from common.network.sse.sse_helper                          import SseHelper
from common.cache.redis_stream.redis_key_builder            import RedisKeyBuilder

class JobSubscription:
    TERMINAL_STATUS_SET = {"completed", "failed", "cancelled"}

    def __init__(self, redis_stream_client : RedisStreamClient, job_configuration : JobConfiguration, job_repository : JobRepository, job_message_repository : JobMessageRepository, job_event_repository : JobEventRepository, job_chunk_repository : JobChunkRepository) -> None:
        self.redis_stream_client    = redis_stream_client
        self.job_configuration      = job_configuration
        self.job_repository         = job_repository
        self.job_message_repository = job_message_repository
        self.job_event_repository   = job_event_repository
        self.job_chunk_repository   = job_chunk_repository

    @staticmethod
    def _create_format_adapter(run_id : uuid.UUID, output_format : str, model_name : str, created_at : Optional[str], completed_at : Optional[str]) -> Union[DeepagentsFormatAdapter, OpenaiResponsesFormatAdapter]:
        normalized_output_format = output_format.lower()
        if normalized_output_format == "deepagents":
            return DeepagentsFormatAdapter(run_id = str(run_id))
        if normalized_output_format == "openai":
            return OpenaiResponsesFormatAdapter(run_id = str(run_id), model_name = model_name, created_at = created_at, completed_at = completed_at)
        raise ValueError(f"UNSUPPORTED OUTPUT FORMAT : {output_format}")

    @staticmethod
    def _format_projection_list(projection_list : List[Dict[str, Any]], event_sequence_number : int) -> List[str]:
        return [
            SseHelper.format_event(
                event_name      = str(projection_dictionary["event_name"]),
                data_dictionary = projection_dictionary["data_dictionary"],
                event_id        = event_sequence_number if projection_index == len(projection_list) - 1 else None
            )
            for projection_index, projection_dictionary in enumerate(projection_list)
        ]

    @staticmethod
    def _is_terminal_status(status : Optional[str]) -> bool:
        return str(status or "").lower() in JobSubscription.TERMINAL_STATUS_SET

    @staticmethod
    def _get_meta_last_sequence_number(meta_dictionary : Dict[str, str]) -> int:
        last_sequence_value = meta_dictionary.get("last_seq")
        return int(last_sequence_value) if last_sequence_value else 0

    @staticmethod
    def _deserialize_dictionary(serialized_value : str) -> Dict[str, Any]:
        deserialized_value = json.loads(serialized_value)
        if isinstance(deserialized_value, dict):
            return deserialized_value
        return {"value" : deserialized_value}

    @staticmethod
    def _deserialize_ns_list(serialized_value : str) -> List[str]:
        deserialized_value = json.loads(serialized_value)
        if not isinstance(deserialized_value, list):
            return []
        return [str(ns_segment) for ns_segment in deserialized_value]

    @staticmethod
    def _create_normalized_chunk_dictionary(field_dictionary : Dict[str, str], sequence_number : int) -> Dict[str, Any]:
        namespace_list = JobSubscription._deserialize_ns_list(field_dictionary.get("ns") or "[]")
        return {
            "seq"             : sequence_number,
            "chunk_type"      : str(field_dictionary.get("chunk_type") or ""),
            "ns_list"         : namespace_list,
            "ns_path"         : "/".join(namespace_list),
            "task_id"         : field_dictionary.get("task_id") or None,
            "parent_task_id"  : field_dictionary.get("parent_task_id") or None,
            "task_link_type"  : field_dictionary.get("task_link_type") or None,
            "data_dictionary" : JobSubscription._deserialize_dictionary(field_dictionary.get("data") or "{}"),
            "created_at"      : field_dictionary.get("created_at")
        }

    @staticmethod
    def _create_stored_chunk_dictionary(chunk_dictionary : Dict[str, Any]) -> Dict[str, Any]:
        namespace_list_value = chunk_dictionary.get("ns_list")
        if isinstance(namespace_list_value, list):
            namespace_list = [str(ns_segment) for ns_segment in namespace_list_value]
        else:
            namespace_path_value = str(chunk_dictionary.get("ns_path") or "")
            namespace_list       = namespace_path_value.split("/") if namespace_path_value else []
        data_value = chunk_dictionary.get("data")
        if isinstance(data_value, dict):
            data_dictionary = data_value
        else:
            data_dictionary = {"value" : data_value}
        return {
            "seq"             : int(chunk_dictionary["seq"]),
            "chunk_type"      : str(chunk_dictionary["chunk_type"]),
            "ns_list"         : namespace_list,
            "ns_path"         : str(chunk_dictionary.get("ns_path") or ""),
            "task_id"         : chunk_dictionary.get("task_id"),
            "parent_task_id"  : chunk_dictionary.get("parent_task_id"),
            "task_link_type"  : chunk_dictionary.get("task_link_type"),
            "data_dictionary" : data_dictionary,
            "created_at"      : chunk_dictionary.get("created_at")
        }

    async def _is_postgresql_terminal_async(self, run_id : uuid.UUID) -> bool:
        job_dictionary = await self.job_repository.get_job_async(run_id)
        return job_dictionary is not None and JobSubscription._is_terminal_status(job_dictionary.get("status"))

    async def _should_fallback_for_missing_stream_async(self, meta_key : str, stream_key : str, initial_meta_dictionary : Dict[str, str]) -> bool:
        confirmed_meta_dictionary = await self.redis_stream_client.get_hash_dictionary_async(meta_key)
        is_stream_exists          = await self.redis_stream_client.is_key_exists_async(stream_key)
        if is_stream_exists:
            return False
        actual_meta_dictionary = confirmed_meta_dictionary or initial_meta_dictionary
        if actual_meta_dictionary and not JobSubscription._is_terminal_status(actual_meta_dictionary.get("status")):
            return JobSubscription._get_meta_last_sequence_number(actual_meta_dictionary) > 0
        return True

    async def _stream_postgresql_fallback_async(self, run_id : uuid.UUID, progress_dictionary : Dict[str, Any], format_adapter : Union[DeepagentsFormatAdapter, OpenaiResponsesFormatAdapter], include_events : bool) -> AsyncIterator[str]:
        job_dictionary = await self.job_repository.get_job_async(run_id)
        if job_dictionary is None:
            raise ValueError(f"JOB NOT FOUND : {run_id}")
        chunk_dictionary_list       = await self.job_chunk_repository.get_chunk_list_after_sequence_async(run_id, progress_dictionary["last_sequence_number"], 1000000)
        last_source_sequence_number = int(job_dictionary.get("last_sequence_number") or 0)
        for chunk_dictionary in chunk_dictionary_list:
            sequence_number = int(chunk_dictionary["seq"])
            is_prior_sequence = sequence_number <= progress_dictionary["last_sequence_number"]
            if is_prior_sequence and not progress_dictionary["is_replay_required"]:
                continue
            projection_list : List[Dict[str, Any]] = []
            if isinstance(format_adapter, OpenaiResponsesFormatAdapter):
                format_adapter.set_source_sequence_number(sequence_number)
            normalized_chunk_dictionary = JobSubscription._create_stored_chunk_dictionary(chunk_dictionary)
            projection_list.extend(format_adapter.format_chunk(normalized_chunk_dictionary, include_events))
            if is_prior_sequence:
                continue
            progress_dictionary["last_sequence_number"] = sequence_number
            for sse_text in JobSubscription._format_projection_list(projection_list, sequence_number):
                yield sse_text
        progress_dictionary["is_replay_required"] = False
        if not JobSubscription._is_terminal_status(job_dictionary.get("status")):
            return
        end_sequence_number = last_source_sequence_number + 1
        if end_sequence_number <= progress_dictionary["last_sequence_number"]:
            return
        usage_dictionary = job_dictionary.get("usage")
        if not isinstance(usage_dictionary, dict):
            usage_dictionary = None
        if isinstance(format_adapter, OpenaiResponsesFormatAdapter):
            completed_at = str(job_dictionary.get("completed_at") or "") or None
            format_adapter.set_completed_at(completed_at)
            format_adapter.set_source_sequence_number(end_sequence_number)
        end_projection_list = format_adapter.format_end(
            status           = str(job_dictionary.get("status")),
            error_message    = job_dictionary.get("error_message"),
            usage_dictionary = usage_dictionary
        )
        progress_dictionary["last_sequence_number"] = end_sequence_number
        for sse_text in JobSubscription._format_projection_list(end_projection_list, end_sequence_number):
            yield sse_text

    async def _stream_postgresql_until_terminal_async(self, run_id : uuid.UUID, progress_dictionary : Dict[str, Any], format_adapter : Union[DeepagentsFormatAdapter, OpenaiResponsesFormatAdapter], include_events : bool) -> AsyncIterator[str]:
        while True:
            async for sse_text in self._stream_postgresql_fallback_async(run_id, progress_dictionary, format_adapter, include_events):
                yield sse_text
            if await self._is_postgresql_terminal_async(run_id):
                async for sse_text in self._stream_postgresql_fallback_async(run_id, progress_dictionary, format_adapter, include_events):
                    yield sse_text
                return
            await asyncio.sleep(self.job_configuration.xread_block_millisecond_count / 1000.0)

    async def subscribe_async(self, run_id : uuid.UUID, last_event_sequence_number : int, output_format : str, include_events : bool, is_resume : bool = False) -> AsyncIterator[str]:
        if last_event_sequence_number < 0:
            raise ValueError(f"INVALID LAST EVENT SEQUENCE NUMBER : {last_event_sequence_number}")
        job_dictionary = await self.job_repository.get_job_async(run_id)
        if job_dictionary is None:
            raise ValueError(f"JOB NOT FOUND : {run_id}")
        request_payload_dictionary           = job_dictionary.get("request_payload") or {}
        model_dictionary                     = request_payload_dictionary.get("model") or {}
        model_name                           = str(model_dictionary.get("model_name") or "unknown")
        created_at                           = str(job_dictionary.get("created_at") or "") or None
        completed_at                         = str(job_dictionary.get("completed_at") or "") or None
        format_adapter                       = JobSubscription._create_format_adapter(run_id, output_format, model_name, created_at, completed_at)
        last_processed_sequence_number       = last_event_sequence_number
        progress_dictionary : Dict[str, Any] = {
            "last_sequence_number" : last_event_sequence_number,
            "is_replay_required"   : last_event_sequence_number > 0
        }
        has_formatted_redis_chunk = False
        is_first_stream_entry     = True
        start_projection_list     = format_adapter.format_start()
        if not is_resume:
            for sse_text in JobSubscription._format_projection_list(start_projection_list, 0):
                yield sse_text
        run_id_string = str(run_id)
        meta_key      = RedisKeyBuilder.get_job_meta_key(run_id_string)
        stream_key    = RedisKeyBuilder.get_job_stream_key(run_id_string)
        try:
            meta_dictionary  = await self.redis_stream_client.get_hash_dictionary_async(meta_key)
            is_stream_exists = await self.redis_stream_client.is_key_exists_async(stream_key)
            if not is_stream_exists and await self._should_fallback_for_missing_stream_async(meta_key, stream_key, meta_dictionary):
                async for sse_text in self._stream_postgresql_until_terminal_async(run_id, progress_dictionary, format_adapter, include_events):
                    yield sse_text
                return
            last_entry_id = "0-0"
            while True:
                stream_entry_list = await self.redis_stream_client.read_stream_async(stream_key, last_entry_id, self.job_configuration.xread_block_millisecond_count)
                if stream_entry_list:
                    for entry_id, field_dictionary in stream_entry_list:
                        last_entry_id      = entry_id
                        sequence_number    = int(field_dictionary.get("seq") or "0")
                        chunk_type         = str(field_dictionary.get("chunk_type") or "")
                        has_trimmed_prefix = is_first_stream_entry and sequence_number > 1
                        has_cursor_gap     = is_first_stream_entry and sequence_number > last_processed_sequence_number + 1
                        if has_cursor_gap or (is_resume and has_trimmed_prefix):
                            progress_dictionary["last_sequence_number"] = last_processed_sequence_number
                            async for sse_text in self._stream_postgresql_until_terminal_async(run_id, progress_dictionary, format_adapter, include_events):
                                yield sse_text
                            return
                        is_first_stream_entry = False
                        if sequence_number <= last_processed_sequence_number:
                            if chunk_type == "__end__":
                                return
                            normalized_chunk_dictionary = JobSubscription._create_normalized_chunk_dictionary(field_dictionary, sequence_number)
                            format_adapter.format_chunk(normalized_chunk_dictionary, include_events)
                            has_formatted_redis_chunk = True
                            continue
                        if chunk_type == "__end__":
                            progress_dictionary["last_sequence_number"] = last_processed_sequence_number
                            progress_dictionary["is_replay_required"]   = progress_dictionary["is_replay_required"] and not has_formatted_redis_chunk
                            async for sse_text in self._stream_postgresql_until_terminal_async(run_id, progress_dictionary, format_adapter, include_events):
                                yield sse_text
                            return
                        last_processed_sequence_number = sequence_number
                        normalized_chunk_dictionary    = JobSubscription._create_normalized_chunk_dictionary(field_dictionary, sequence_number)
                        projection_list                = format_adapter.format_chunk(normalized_chunk_dictionary, include_events)
                        has_formatted_redis_chunk      = True
                        for sse_text in JobSubscription._format_projection_list(projection_list, sequence_number):
                            yield sse_text
                    continue
                if await self._is_postgresql_terminal_async(run_id):
                    progress_dictionary["last_sequence_number"] = last_processed_sequence_number
                    progress_dictionary["is_replay_required"  ] = progress_dictionary["is_replay_required"] and not has_formatted_redis_chunk
                    async for sse_text in self._stream_postgresql_until_terminal_async(run_id, progress_dictionary, format_adapter, include_events):
                        yield sse_text
                    return
                is_stream_exists = await self.redis_stream_client.is_key_exists_async(stream_key)
                if is_stream_exists:
                    continue
                meta_dictionary = await self.redis_stream_client.get_hash_dictionary_async(meta_key)
                if not await self._should_fallback_for_missing_stream_async(meta_key, stream_key, meta_dictionary):
                    continue
                progress_dictionary["last_sequence_number"] = last_processed_sequence_number
                progress_dictionary["is_replay_required"  ] = progress_dictionary["is_replay_required"] and not has_formatted_redis_chunk
                async for sse_text in self._stream_postgresql_until_terminal_async(run_id, progress_dictionary, format_adapter, include_events):
                    yield sse_text
                return
        except RedisError:
            progress_dictionary["last_sequence_number"] = last_processed_sequence_number
            progress_dictionary["is_replay_required"  ] = progress_dictionary["is_replay_required"] and not has_formatted_redis_chunk
            async for sse_text in self._stream_postgresql_until_terminal_async(run_id, progress_dictionary, format_adapter, include_events):
                yield sse_text
