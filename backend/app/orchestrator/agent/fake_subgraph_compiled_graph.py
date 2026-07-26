##################################################
# 가상 서브그래프 컴파일 그래프 (트리 구조 스트리밍 예시)
# 메인 에이전트가 task() 로 서브에이전트(web-researcher)에 위임했을 때
# astream(subgraphs=True) 이 실제로 뱉는 다단계 네임스페이스 청크 흐름을 재현한다.
#
# [네임스페이스 트리 구조]
#   ()                                  : 메인 에이전트 (루트, ns_path = "")
#   ("task:aaa",)                       : 서브에이전트 1단계 (ns_path = "task:aaa")
#   ("task:aaa", "tools:bbb")           : 서브에이전트 내부 도구 노드 2단계 (ns_path = "task:aaa|tools:bbb")
#
# 파이프라인(ChunkSerializeHelper → RedisChunkBuffer → SSE → ChunkFlushService)이
# 모든 계층의 청크를 누실 없이 적재·전송·병합하는지 검증하는 데 사용한다.
##################################################

import uuid

# uv add langchain-core
from typing                  import Any
from typing                  import AsyncIterator
from typing                  import Dict
from typing                  import List
from langchain_core.messages import AIMessageChunk


class FakeSubgraphCompiledGraph:
    async def astream(self, input_dictionary : Dict[str, Any], runnable_configuration : Dict[str, Any], stream_mode : List[str] = None, subgraphs : bool = False, version : str = "v2") -> AsyncIterator[Dict[str, Any]]:
        root_message_id     = f"ai-root-{uuid.uuid4()}"
        subagent_message_id = f"ai-sub-{uuid.uuid4()}"

        # ① 루트 : 메인 에이전트가 서브에이전트 위임(task 도구 호출)을 시작한다
        yield {"type" : "tasks", "ns" : (), "data" : {"id" : "main-task-1", "name" : "model", "input" : {"question" : "서울 날씨"}}}

        # ② 서브그래프 1단계 : web-researcher 서브에이전트 실행 시작 (ns 에 task 네임스페이스가 쌓인다)
        yield {"type" : "tasks", "ns" : ("task:aaa",), "data" : {"id" : "sub-task-1", "name" : "web-researcher", "input" : {"query" : "서울 날씨"}}}

        # ③ 서브그래프 2단계 : 서브에이전트 내부의 검색 도구 노드 (ns 가 2단계로 쌓인다)
        yield {"type" : "custom", "ns" : ("task:aaa", "tools:bbb"), "data" : {"stage" : "tavily_search", "query" : "서울 날씨"}}

        # ④ 서브그래프 1단계 : 서브에이전트의 토큰 스트리밍 (루트가 아니므로 표시용 저장에서 제외되어야 한다)
        yield {"type" : "messages", "ns" : ("task:aaa",), "data" : (AIMessageChunk(content = "검색 결과 정리 중...", id = subagent_message_id), {"langgraph_node" : "model"})}

        # ⑤ 서브그래프 1단계 : 서브에이전트 실행 종료
        yield {"type" : "tasks", "ns" : ("task:aaa",), "data" : {"id" : "sub-task-1", "name" : "web-researcher", "result" : "completed"}}

        # ⑥ 루트 : 메인 에이전트가 서브에이전트 보고를 반영해 최종 답변을 스트리밍한다
        yield {"type" : "messages", "ns" : (), "data" : (AIMessageChunk(content = "서울은 ", id = root_message_id), {"langgraph_node" : "model"})}
        yield {"type" : "messages", "ns" : (), "data" : (AIMessageChunk(content = "맑음입니다.", id = root_message_id), {"langgraph_node" : "model"})}

        # ⑦ 루트 : 상태 스냅샷 + 메인 태스크 종료
        yield {"type" : "values", "ns" : (), "data" : {"messages" : [{"role" : "ai", "content" : "서울은 맑음입니다."}]}}
        yield {"type" : "tasks", "ns" : (), "data" : {"id" : "main-task-1", "name" : "model", "result" : "completed"}}
