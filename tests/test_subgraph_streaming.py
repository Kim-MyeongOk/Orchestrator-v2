##################################################
# 서브그래프(트리 구조) 스트리밍 파이프라인 테스트
# FakeSubgraphCompiledGraph 가 재현하는 다단계 네임스페이스 청크가
# GraphStreamExecutor → (버퍼 누적 + SSE yield) → ChunkFlushService 병합 규칙까지
# 누실 없이 흐르는지 검증한다. Redis 대신 동일 인터페이스의 인메모리 버퍼를 사용한다.
#
# 실행 : .venv\Scripts\python.exe -m pytest -v
##################################################

import asyncio
import json
import uuid

from app.orchestrator.agent.fake_subgraph_compiled_graph import FakeSubgraphCompiledGraph
from app.orchestrator.service.graph_stream_executor      import GraphStreamExecutor
from app.orchestrator.service.chunk_flush_service        import ChunkFlushService


class InMemoryChunkBuffer:
    # RedisChunkBuffer 와 동일 인터페이스의 인메모리 대역 (JSON 직렬화 왕복까지 재현해 직렬화 회귀를 잡는다)
    def __init__(self):
        self._chunk_json_dictionary = {}

    @staticmethod
    def _create_chunk_list_key(thread_id, run_id):
        return f"{thread_id}:{run_id}"

    async def append_chunk_async(self, thread_id, run_id, chunk_dictionary):
        chunk_list_key = InMemoryChunkBuffer._create_chunk_list_key(thread_id, run_id)
        self._chunk_json_dictionary.setdefault(chunk_list_key, []).append(json.dumps(chunk_dictionary, ensure_ascii = False, default = str))

    async def get_chunk_dictionary_list_async(self, thread_id, run_id):
        chunk_list_key = InMemoryChunkBuffer._create_chunk_list_key(thread_id, run_id)
        return [json.loads(chunk_json) for chunk_json in self._chunk_json_dictionary.get(chunk_list_key, [])]

    async def delete_buffer_async(self, thread_id, run_id):
        self._chunk_json_dictionary.pop(InMemoryChunkBuffer._create_chunk_list_key(thread_id, run_id), None)


def _execute_subgraph_stream():
    # 실행기 파이프라인을 관통시켜 (SSE 로 흘러나간 청크, 버퍼에 적재된 청크) 를 함께 수집한다
    async def execute_async():
        in_memory_chunk_buffer = InMemoryChunkBuffer()
        graph_stream_executor  = GraphStreamExecutor(redis_chunk_buffer = in_memory_chunk_buffer)
        thread_id              = uuid.uuid4()
        run_id                 = uuid.uuid4()

        streamed_chunk_dictionary_list = []
        async for chunk_dictionary in graph_stream_executor.execute_graph_stream_async(FakeSubgraphCompiledGraph(), thread_id, run_id, []):
            streamed_chunk_dictionary_list.append(chunk_dictionary)

        buffered_chunk_dictionary_list = await in_memory_chunk_buffer.get_chunk_dictionary_list_async(thread_id, run_id)
        return streamed_chunk_dictionary_list, buffered_chunk_dictionary_list
    return asyncio.run(execute_async())


class TestSubgraphChunkPipeline:
    def test_no_chunk_loss_between_stream_and_buffer(self):
        # SSE 로 나간 청크와 버퍼에 적재된 청크가 개수·내용 모두 일치해야 한다 (누실 없음)
        streamed_chunk_dictionary_list, buffered_chunk_dictionary_list = _execute_subgraph_stream()
        assert len(streamed_chunk_dictionary_list) == 9
        assert len(buffered_chunk_dictionary_list) == 9
        assert streamed_chunk_dictionary_list      == buffered_chunk_dictionary_list

    def test_namespace_path_stacked_as_tree(self):
        # 루트("") / 1단계("task:aaa") / 2단계("task:aaa|tools:bbb") 네임스페이스가 모두 관측되어야 한다
        streamed_chunk_dictionary_list, _buffered = _execute_subgraph_stream()
        namespace_path_set = {chunk_dictionary["namespace_path"] for chunk_dictionary in streamed_chunk_dictionary_list}
        assert namespace_path_set == {"", "task:aaa", "task:aaa|tools:bbb"}

    def test_subagent_task_chunks_carry_namespace(self):
        # 서브에이전트 tasks 청크는 1단계 네임스페이스를 유지한 채 적재되어야 한다
        _streamed, buffered_chunk_dictionary_list = _execute_subgraph_stream()
        subagent_task_list = [chunk_dictionary for chunk_dictionary in buffered_chunk_dictionary_list if chunk_dictionary["chunk_type"] == "tasks" and chunk_dictionary["namespace_path"] == "task:aaa"]
        assert len(subagent_task_list) == 2
        assert subagent_task_list[0]["payload"]["name"] == "web-researcher"

    def test_flush_merge_separates_root_and_subagent_messages(self):
        # 병합 규칙 : 루트 메시지만 is_root_message=True, 서브에이전트 메시지는 ns_path 를 보존한 채 False
        _streamed, buffered_chunk_dictionary_list = _execute_subgraph_stream()
        merged_message_dictionary_list            = ChunkFlushService._create_merged_message_dictionary_list(buffered_chunk_dictionary_list)
        root_flag_dictionary                      = {merged_message["ns_path"] : merged_message["is_root_message"] for merged_message in merged_message_dictionary_list}
        assert root_flag_dictionary[""]           is True   # 루트 : "서울은 맑음입니다." (2조각 병합)
        assert root_flag_dictionary["task:aaa"]   is False  # 서브에이전트 : "검색 결과 정리 중..."
        root_merged_message = next(merged_message for merged_message in merged_message_dictionary_list if merged_message["is_root_message"])
        assert root_merged_message["content"] == "서울은 맑음입니다."

    def test_aggregated_event_preserves_tree_namespaces(self):
        # tasks / custom 집계 시 각 이벤트의 namespace_path 가 트리 계층 그대로 남아야 한다
        _streamed, buffered_chunk_dictionary_list = _execute_subgraph_stream()
        aggregated_event_dictionary               = ChunkFlushService._create_aggregated_event_dictionary(buffered_chunk_dictionary_list)
        task_namespace_path_list                  = [task_event["namespace_path"] for task_event in aggregated_event_dictionary["tasks"]]
        custom_namespace_path_list                = [custom_event["namespace_path"] for custom_event in aggregated_event_dictionary["custom"]]
        assert task_namespace_path_list   == ["", "task:aaa", "task:aaa", ""]
        assert custom_namespace_path_list == ["task:aaa|tools:bbb"]

    def test_last_values_snapshot_from_root(self):
        # values 스냅샷(final_output 후보)은 루트 네임스페이스에서 온 마지막 것이어야 한다
        _streamed, buffered_chunk_dictionary_list = _execute_subgraph_stream()
        last_values_dictionary                    = ChunkFlushService._extract_last_values_dictionary(buffered_chunk_dictionary_list)
        assert last_values_dictionary == {"messages" : [{"role" : "ai", "content" : "서울은 맑음입니다."}]}
