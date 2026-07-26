from dataclasses import replace
from typing      import Any
from typing      import Dict
from typing      import List
from typing      import Optional
from typing      import Set
from typing      import Tuple

from app.llm.stream_pipeline.normalized_chunk import NormalizedChunk

class ChunkTaskCorrelationResolver:
    def __init__(self) -> None:
        self._active_task_id_set_dictionary : Dict[str, Set[str]] = {}

    @staticmethod
    def _parse_namespace_segment(namespace_segment : str) -> Tuple[Optional[str], Optional[str]]:
        node_name, separator, task_id = namespace_segment.rpartition(":")
        if not separator or not node_name or not task_id:
            return None, None
        return node_name, task_id

    @staticmethod
    def _get_parent_task_id(namespace_list : List[str]) -> Optional[str]:
        if not namespace_list:
            return None
        _node_name, task_id = ChunkTaskCorrelationResolver._parse_namespace_segment(namespace_list[-1])
        return task_id

    @staticmethod
    def _get_checkpoint_namespace_list(metadata_dictionary : Dict[str, Any]) -> List[str]:
        checkpoint_namespace = metadata_dictionary.get("langgraph_checkpoint_ns")
        if checkpoint_namespace is None:
            return []
        if isinstance(checkpoint_namespace, str):
            return [namespace_segment for namespace_segment in checkpoint_namespace.split("|") if namespace_segment]
        if isinstance(checkpoint_namespace, list):
            return [str(namespace_segment) for namespace_segment in checkpoint_namespace]
        return []

    @staticmethod
    def _get_task_status(normalized_chunk : NormalizedChunk) -> str:
        data_dictionary = normalized_chunk.data_dictionary
        if normalized_chunk.chunk_type != "tasks":
            return "unknown"
        if data_dictionary.get("interrupts"):
            return "interrupted"
        if data_dictionary.get("error"):
            return "failed"
        if "result" in data_dictionary:
            return "completed"
        return "running"

    def _add_active_task_id(self, namespace_path : str, task_id : str) -> None:
        task_id_set = self._active_task_id_set_dictionary.get(namespace_path)
        if task_id_set is None:
            task_id_set = set()
            self._active_task_id_set_dictionary[namespace_path] = task_id_set
        task_id_set.add(task_id)

    def _remove_active_task_id(self, namespace_path : str, task_id : str) -> None:
        task_id_set = self._active_task_id_set_dictionary.get(namespace_path)
        if task_id_set is None:
            return
        task_id_set.discard(task_id)
        if not task_id_set:
            self._active_task_id_set_dictionary.pop(namespace_path, None)

    def _resolve_tasks_chunk(self, normalized_chunk : NormalizedChunk) -> NormalizedChunk:
        task_id_value  = normalized_chunk.data_dictionary.get("id")
        task_id        = str(task_id_value) if task_id_value is not None else None
        parent_task_id = ChunkTaskCorrelationResolver._get_parent_task_id(normalized_chunk.namespace_list)
        if task_id is None:
            return replace(normalized_chunk, parent_task_id = parent_task_id, task_link_type = "unassigned")
        if ChunkTaskCorrelationResolver._get_task_status(normalized_chunk) == "running":
            self._add_active_task_id(normalized_chunk.namespace_path, task_id)
        else:
            self._remove_active_task_id(normalized_chunk.namespace_path, task_id)
        return replace(
            normalized_chunk,
            task_id        = task_id,
            parent_task_id = parent_task_id,
            task_link_type = "explicit"
        )

    def _resolve_messages_chunk(self, normalized_chunk : NormalizedChunk) -> NormalizedChunk:
        metadata_dictionary = normalized_chunk.data_dictionary.get("metadata")
        if not isinstance(metadata_dictionary, dict):
            return replace(normalized_chunk, task_link_type = "unassigned")
        checkpoint_namespace_list = ChunkTaskCorrelationResolver._get_checkpoint_namespace_list(metadata_dictionary)
        if not checkpoint_namespace_list:
            parent_task_id = ChunkTaskCorrelationResolver._get_parent_task_id(normalized_chunk.namespace_list)
            return replace(normalized_chunk, parent_task_id = parent_task_id, task_link_type = "namespace" if parent_task_id is not None else "unassigned")
        _node_name, task_id = ChunkTaskCorrelationResolver._parse_namespace_segment(checkpoint_namespace_list[-1])
        parent_task_id = None
        if len(checkpoint_namespace_list) >= 2:
            _parent_node_name, parent_task_id = ChunkTaskCorrelationResolver._parse_namespace_segment(checkpoint_namespace_list[-2])
        return replace(
            normalized_chunk,
            task_id        = task_id,
            parent_task_id = parent_task_id,
            task_link_type = "metadata" if task_id is not None else "unassigned"
        )

    def _resolve_custom_chunk(self, normalized_chunk : NormalizedChunk) -> NormalizedChunk:
        task_id_value = normalized_chunk.data_dictionary.get("task_id")
        if task_id_value is not None:
            return replace(
                normalized_chunk,
                task_id        = str(task_id_value),
                parent_task_id = ChunkTaskCorrelationResolver._get_parent_task_id(normalized_chunk.namespace_list),
                task_link_type = "explicit"
            )
        task_id_set = self._active_task_id_set_dictionary.get(normalized_chunk.namespace_path) or set()
        if len(task_id_set) == 1:
            return replace(
                normalized_chunk,
                task_id        = next(iter(task_id_set)),
                parent_task_id = ChunkTaskCorrelationResolver._get_parent_task_id(normalized_chunk.namespace_list),
                task_link_type = "inferred"
            )
        return replace(
            normalized_chunk,
            parent_task_id = ChunkTaskCorrelationResolver._get_parent_task_id(normalized_chunk.namespace_list),
            task_link_type = "unassigned"
        )

    def resolve(self, normalized_chunk : NormalizedChunk) -> NormalizedChunk:
        if normalized_chunk.chunk_type == "tasks":
            return self._resolve_tasks_chunk(normalized_chunk)
        if normalized_chunk.chunk_type == "messages":
            return self._resolve_messages_chunk(normalized_chunk)
        if normalized_chunk.chunk_type == "custom":
            return self._resolve_custom_chunk(normalized_chunk)
        return normalized_chunk
