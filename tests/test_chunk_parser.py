##################################################
# 청크 파서 / 병합 규칙 유닛 테스트
# DB / Redis 연결 없이 순수 함수만 검증한다.
#
# [그룹 A] ChunkSerializeHelper : langgraph 1.x dict 포맷 + 구버전 tuple 포맷 파싱
# [그룹 B] ChunkFlushService    : values 최신 선택 / tasks·custom 집계 / messages 병합 규칙
# [그룹 C] FakeCompiledGraph    : 가짜 그래프 청크가 실제 파서로 전량 파싱되는지 통합 검증
#
# 실행 : .venv\Scripts\python.exe -m pytest -v
##################################################

import asyncio

from langchain_core.messages import AIMessageChunk
from langchain_core.messages import HumanMessage

from app.orchestrator.agent.fake_compiled_graph      import FakeCompiledGraph
from app.orchestrator.service.chunk_serialize_helper import ChunkSerializeHelper
from app.orchestrator.service.chunk_flush_service    import ChunkFlushService


##################################################
# 그룹 A : ChunkSerializeHelper 파싱 검증
##################################################

class TestParseStreamChunk:
    def test_dict_format_values_chunk(self):
        # langgraph 1.x dict 포맷 : {'type', 'ns', 'data'}
        stream_chunk     = {"type" : "values", "ns" : (), "data" : {"messages" : [{"role" : "ai", "content" : "안녕"}]}}
        chunk_dictionary = ChunkSerializeHelper.create_chunk_dictionary(stream_chunk)
        assert chunk_dictionary is not None
        assert chunk_dictionary["chunk_type"]     == "values"
        assert chunk_dictionary["namespace_path"] == ""
        assert chunk_dictionary["payload"]        == {"messages" : [{"role" : "ai", "content" : "안녕"}]}

    def test_dict_format_tasks_chunk(self):
        stream_chunk     = {"type" : "tasks", "ns" : (), "data" : {"id" : "task-1", "name" : "agent"}}
        chunk_dictionary = ChunkSerializeHelper.create_chunk_dictionary(stream_chunk)
        assert chunk_dictionary is not None
        assert chunk_dictionary["chunk_type"] == "tasks"
        assert chunk_dictionary["payload"]    == {"id" : "task-1", "name" : "agent"}

    def test_dict_format_custom_chunk(self):
        stream_chunk     = {"type" : "custom", "ns" : (), "data" : {"progress_percent" : 50}}
        chunk_dictionary = ChunkSerializeHelper.create_chunk_dictionary(stream_chunk)
        assert chunk_dictionary is not None
        assert chunk_dictionary["chunk_type"] == "custom"

    def test_dict_format_namespace_tuple_joined_with_pipe(self):
        # 서브그래프 네임스페이스 튜플은 "|" 로 join 되어 namespace_path 가 된다
        stream_chunk     = {"type" : "custom", "ns" : ("parent:1", "child:2"), "data" : {"stage" : "sub"}}
        chunk_dictionary = ChunkSerializeHelper.create_chunk_dictionary(stream_chunk)
        assert chunk_dictionary is not None
        assert chunk_dictionary["namespace_path"] == "parent:1|child:2"

    def test_dict_format_none_namespace_treated_as_root(self):
        # ns 가 None 이어도 루트("") 로 처리되어야 한다
        stream_chunk     = {"type" : "custom", "ns" : None, "data" : {"stage" : "root"}}
        chunk_dictionary = ChunkSerializeHelper.create_chunk_dictionary(stream_chunk)
        assert chunk_dictionary is not None
        assert chunk_dictionary["namespace_path"] == ""

    def test_dict_format_messages_chunk(self):
        # messages 모드의 data 는 (message_chunk, metadata) 튜플이다
        message_chunk    = AIMessageChunk(content = "안녕하세요", id = "ai-message-1")
        stream_chunk     = {"type" : "messages", "ns" : (), "data" : (message_chunk, {"langgraph_node" : "agent"})}
        chunk_dictionary = ChunkSerializeHelper.create_chunk_dictionary(stream_chunk)
        assert chunk_dictionary is not None
        assert chunk_dictionary["chunk_type"] == "messages"
        assert chunk_dictionary["message_id"] == "ai-message-1"
        assert chunk_dictionary["role"]       == "ai"
        assert chunk_dictionary["content"]    == "안녕하세요"

    def test_legacy_three_tuple_format(self):
        # 구버전 (namespace_tuple, stream_mode, payload) 3-tuple 호환
        stream_chunk     = (("parent:1",), "tasks", {"id" : "task-1"})
        chunk_dictionary = ChunkSerializeHelper.create_chunk_dictionary(stream_chunk)
        assert chunk_dictionary is not None
        assert chunk_dictionary["chunk_type"]     == "tasks"
        assert chunk_dictionary["namespace_path"] == "parent:1"
        assert chunk_dictionary["payload"]        == {"id" : "task-1"}

    def test_legacy_two_tuple_format(self):
        # 구버전 (stream_mode, payload) 2-tuple 호환 — 루트 네임스페이스로 처리된다
        stream_chunk     = ("values", {"messages" : []})
        chunk_dictionary = ChunkSerializeHelper.create_chunk_dictionary(stream_chunk)
        assert chunk_dictionary is not None
        assert chunk_dictionary["chunk_type"]     == "values"
        assert chunk_dictionary["namespace_path"] == ""

    def test_unparseable_input_returns_none(self):
        # 파싱 불가 입력은 None 을 반환하여 파이프라인이 조용히 건너뛴다
        assert ChunkSerializeHelper.create_chunk_dictionary("not-a-chunk")            is None
        assert ChunkSerializeHelper.create_chunk_dictionary(None)                     is None
        assert ChunkSerializeHelper.create_chunk_dictionary(("only-one",))            is None
        assert ChunkSerializeHelper.create_chunk_dictionary(("a", "b", "c", "d"))     is None
        assert ChunkSerializeHelper.create_chunk_dictionary({"no_type_key" : "here"}) is None


class TestCreateJsonSafeValue:
    def test_primitive_values_pass_through(self):
        assert ChunkSerializeHelper.create_json_safe_value(None)    is None
        assert ChunkSerializeHelper.create_json_safe_value("텍스트") == "텍스트"
        assert ChunkSerializeHelper.create_json_safe_value(42)      == 42
        assert ChunkSerializeHelper.create_json_safe_value(True)    is True

    def test_base_message_converted_to_dictionary(self):
        # BaseMessage 계열은 message_id / role / content 핵심 필드만 추린 dict 로 강등된다
        human_message   = HumanMessage(content = "질문입니다", id = "human-1")
        json_safe_value = ChunkSerializeHelper.create_json_safe_value(human_message)
        assert json_safe_value == {"message_id" : "human-1", "role" : "human", "content" : "질문입니다"}

    def test_nested_structure_converted_recursively(self):
        ai_message      = AIMessageChunk(content = "응답", id = "ai-1")
        json_safe_value = ChunkSerializeHelper.create_json_safe_value({"messages" : [ai_message], "count" : 1})
        assert json_safe_value["count"]                    == 1
        assert json_safe_value["messages"][0]["role"]      == "ai"
        assert json_safe_value["messages"][0]["content"]   == "응답"

    def test_unserializable_object_demoted_to_string(self):
        # 직렬화 불가 객체는 파이프라인이 죽지 않도록 문자열로 강등된다
        class UnserializableObject:
            def __str__(self):
                return "UNSERIALIZABLE"
        json_safe_value = ChunkSerializeHelper.create_json_safe_value(UnserializableObject())
        assert json_safe_value == "UNSERIALIZABLE"


##################################################
# 그룹 B : ChunkFlushService 병합 규칙 검증
##################################################

class TestExtractLastValuesDictionary:
    def test_last_values_chunk_wins(self):
        # values 청크가 여러 개면 가장 마지막(최신) payload 만 final_output 이 된다
        chunk_dictionary_list = [
            {"chunk_type" : "values", "namespace_path" : "", "payload" : {"messages" : [{"content" : "이전"}]}},
            {"chunk_type" : "tasks" , "namespace_path" : "", "payload" : {"id" : "task-1"}},
            {"chunk_type" : "values", "namespace_path" : "", "payload" : {"messages" : [{"content" : "최신"}]}}
        ]
        last_values_dictionary = ChunkFlushService._extract_last_values_dictionary(chunk_dictionary_list)
        assert last_values_dictionary == {"messages" : [{"content" : "최신"}]}

    def test_no_values_chunk_returns_none(self):
        chunk_dictionary_list = [{"chunk_type" : "tasks", "namespace_path" : "", "payload" : {"id" : "task-1"}}]
        assert ChunkFlushService._extract_last_values_dictionary(chunk_dictionary_list) is None


class TestCreateAggregatedEventDictionary:
    def test_tasks_and_custom_collected_in_order(self):
        # tasks / custom 은 발생 순서대로 전량 수집되고 messages / values 는 제외된다
        chunk_dictionary_list = [
            {"chunk_type" : "tasks"   , "namespace_path" : ""     , "payload" : {"id" : "task-1", "name" : "agent"}},
            {"chunk_type" : "messages", "namespace_path" : ""     , "message_id" : "m1", "role" : "ai", "content" : "무시"},
            {"chunk_type" : "custom"  , "namespace_path" : "sub:1", "payload" : {"progress_percent" : 50}},
            {"chunk_type" : "values"  , "namespace_path" : ""     , "payload" : {"messages" : []}},
            {"chunk_type" : "tasks"   , "namespace_path" : ""     , "payload" : {"id" : "task-1", "result" : "completed"}}
        ]
        aggregated_event_dictionary = ChunkFlushService._create_aggregated_event_dictionary(chunk_dictionary_list)
        assert len(aggregated_event_dictionary["tasks"])  == 2
        assert len(aggregated_event_dictionary["custom"]) == 1
        assert aggregated_event_dictionary["tasks"][0]["payload"]          == {"id" : "task-1", "name" : "agent"}
        assert aggregated_event_dictionary["tasks"][1]["payload"]          == {"id" : "task-1", "result" : "completed"}
        assert aggregated_event_dictionary["custom"][0]["namespace_path"]  == "sub:1"

    def test_empty_chunk_list_produces_empty_groups(self):
        aggregated_event_dictionary = ChunkFlushService._create_aggregated_event_dictionary([])
        assert aggregated_event_dictionary == {"tasks" : [], "custom" : []}


class TestMergeMessageContent:
    def test_string_contents_concatenated(self):
        assert ChunkFlushService._merge_message_content("서울은 ", "대한민국의 수도") == "서울은 대한민국의 수도"

    def test_list_contents_extended(self):
        # 멀티모달 리스트 콘텐츠는 extend 된다
        merged_content = ChunkFlushService._merge_message_content([{"type" : "text", "text" : "a"}], [{"type" : "text", "text" : "b"}])
        assert merged_content == [{"type" : "text", "text" : "a"}, {"type" : "text", "text" : "b"}]

    def test_mixed_types_demoted_to_string(self):
        assert ChunkFlushService._merge_message_content("텍스트", 123) == "텍스트123"


class TestCreateMergedMessageDictionaryList:
    def test_same_message_id_fragments_merged(self):
        # 동일 (ns_path, message_id) 조각은 하나로 병합되고 seq_first / seq_last 좌표가 채워진다
        chunk_dictionary_list = [
            {"chunk_type" : "messages", "namespace_path" : "", "message_id" : "ai-1", "role" : "ai", "content" : "서울은 "},
            {"chunk_type" : "tasks"   , "namespace_path" : "", "payload" : {"id" : "task-1"}},
            {"chunk_type" : "messages", "namespace_path" : "", "message_id" : "ai-1", "role" : "ai", "content" : "수도입니다."}
        ]
        merged_message_dictionary_list = ChunkFlushService._create_merged_message_dictionary_list(chunk_dictionary_list)
        assert len(merged_message_dictionary_list) == 1
        merged_message_dictionary = merged_message_dictionary_list[0]
        assert merged_message_dictionary["message_id"] == "ai-1"
        assert merged_message_dictionary["content"]    == "서울은 수도입니다."
        assert merged_message_dictionary["seq_first"]  == 1
        assert merged_message_dictionary["seq_last"]   == 3

    def test_missing_message_id_gets_synthetic_id(self):
        chunk_dictionary_list = [
            {"chunk_type" : "messages", "namespace_path" : "", "message_id" : None, "role" : "ai", "content" : "아이디 없는 조각"}
        ]
        merged_message_dictionary_list = ChunkFlushService._create_merged_message_dictionary_list(chunk_dictionary_list)
        assert len(merged_message_dictionary_list) == 1
        assert merged_message_dictionary_list[0]["message_id"] == "synthetic-ai-1"

    def test_empty_content_message_dropped(self):
        # tool call 전용 청크 등 본문이 비어 있는 메시지는 저장 대상에서 제외된다
        chunk_dictionary_list = [
            {"chunk_type" : "messages", "namespace_path" : "", "message_id" : "empty-1", "role" : "ai", "content" : ""},
            {"chunk_type" : "messages", "namespace_path" : "", "message_id" : "full-1" , "role" : "ai", "content" : "본문 있음"}
        ]
        merged_message_dictionary_list = ChunkFlushService._create_merged_message_dictionary_list(chunk_dictionary_list)
        assert len(merged_message_dictionary_list) == 1
        assert merged_message_dictionary_list[0]["message_id"] == "full-1"

    def test_only_root_namespace_marked_as_root_message(self):
        chunk_dictionary_list = [
            {"chunk_type" : "messages", "namespace_path" : ""     , "message_id" : "root-1", "role" : "ai", "content" : "루트"},
            {"chunk_type" : "messages", "namespace_path" : "sub:1", "message_id" : "sub-1" , "role" : "ai", "content" : "서브"}
        ]
        merged_message_dictionary_list = ChunkFlushService._create_merged_message_dictionary_list(chunk_dictionary_list)
        root_flag_dictionary           = {merged_message["message_id"] : merged_message["is_root_message"] for merged_message in merged_message_dictionary_list}
        assert root_flag_dictionary["root-1"] is True
        assert root_flag_dictionary["sub-1"]  is False


class TestGetThreadPreview:
    def test_last_root_ai_message_used_as_preview(self):
        merged_message_dictionary_list = [
            {"message_id" : "ai-1", "role" : "ai"   , "is_root_message" : True , "content" : "첫 번째 답변"},
            {"message_id" : "ai-2", "role" : "ai"   , "is_root_message" : False, "content" : "서브그래프 답변"},
            {"message_id" : "ai-3", "role" : "ai"   , "is_root_message" : True , "content" : "마지막 답변"}
        ]
        assert ChunkFlushService._get_thread_preview(merged_message_dictionary_list) == "마지막 답변"

    def test_preview_truncated_to_200_characters(self):
        long_content                   = "가" * 300
        merged_message_dictionary_list = [{"message_id" : "ai-1", "role" : "ai", "is_root_message" : True, "content" : long_content}]
        thread_preview                 = ChunkFlushService._get_thread_preview(merged_message_dictionary_list)
        assert len(thread_preview) == 200

    def test_no_root_ai_message_returns_none(self):
        merged_message_dictionary_list = [{"message_id" : "sub-1", "role" : "ai", "is_root_message" : False, "content" : "서브만 존재"}]
        assert ChunkFlushService._get_thread_preview(merged_message_dictionary_list) is None


##################################################
# 그룹 C : FakeCompiledGraph ↔ 파서 통합 검증
##################################################

class TestFakeCompiledGraphIntegration:
    @staticmethod
    def _collect_parsed_chunk_list():
        # pytest-asyncio 없이 asyncio.run 으로 비동기 스트림을 소비한다
        async def collect_async():
            fake_compiled_graph   = FakeCompiledGraph()
            chunk_dictionary_list = []
            dropped_chunk_count   = 0
            async for stream_chunk in fake_compiled_graph.astream({"messages" : []}, {"configurable" : {"thread_id" : "test-thread"}}, stream_mode = ["tasks", "messages", "values", "custom"], subgraphs = True, version = "v2"):
                chunk_dictionary = ChunkSerializeHelper.create_chunk_dictionary(stream_chunk)
                if chunk_dictionary is None:
                    dropped_chunk_count = dropped_chunk_count + 1
                    continue
                chunk_dictionary_list.append(chunk_dictionary)
            return chunk_dictionary_list, dropped_chunk_count
        return asyncio.run(collect_async())

    def test_all_fake_chunks_parse_without_drop(self):
        # 가짜 그래프의 8개 청크가 실제 파서로 전량 파싱되어야 한다 (dict 포맷 사양 일치 검증)
        chunk_dictionary_list, dropped_chunk_count = TestFakeCompiledGraphIntegration._collect_parsed_chunk_list()
        assert dropped_chunk_count        == 0
        assert len(chunk_dictionary_list) == 8

    def test_chunk_type_distribution(self):
        chunk_dictionary_list, _dropped_chunk_count = TestFakeCompiledGraphIntegration._collect_parsed_chunk_list()
        chunk_type_count_dictionary                 = {}
        for chunk_dictionary in chunk_dictionary_list:
            chunk_type                                   = chunk_dictionary["chunk_type"]
            chunk_type_count_dictionary[chunk_type]      = chunk_type_count_dictionary.get(chunk_type, 0) + 1
        assert chunk_type_count_dictionary == {"tasks" : 2, "messages" : 3, "custom" : 1, "values" : 2}

    def test_message_fragments_merge_into_full_sentence(self):
        # messages 3조각이 동일 message_id 로 병합되어 완전한 문장이 되어야 한다
        chunk_dictionary_list, _dropped_chunk_count = TestFakeCompiledGraphIntegration._collect_parsed_chunk_list()
        merged_message_dictionary_list              = ChunkFlushService._create_merged_message_dictionary_list(chunk_dictionary_list)
        assert len(merged_message_dictionary_list) == 1
        assert merged_message_dictionary_list[0]["content"] == "서울은 대한민국의 수도이며 인구 약 940만 명의 도시입니다."

    def test_last_values_chunk_becomes_final_output(self):
        # values 2개 중 마지막 스냅샷만 final_output 후보가 되어야 한다
        chunk_dictionary_list, _dropped_chunk_count = TestFakeCompiledGraphIntegration._collect_parsed_chunk_list()
        last_values_dictionary                      = ChunkFlushService._extract_last_values_dictionary(chunk_dictionary_list)
        assert last_values_dictionary == {"messages" : [{"role" : "ai", "content" : "서울은 대한민국의 수도이며 인구 약 940만 명의 도시입니다."}]}
