##################################################
# 가상 컴파일 그래프
# workflow.compile() 결과(CompiledStateGraph)를 흉내 내는 가짜 그래프.
# astream 시그니처가 동일하므로 실제 그래프로 교체 시 호출부 수정이 없다.
##################################################

import uuid

# uv add langchain-core
from typing                  import Any
from typing                  import AsyncIterator
from typing                  import Dict
from typing                  import List
from typing                  import Tuple
from langchain_core.messages import AIMessageChunk


class FakeCompiledGraph:
    async def astream(self, input_dictionary : Dict[str, Any], runnable_configuration : Dict[str, Any], stream_mode : List[str] = None, subgraphs : bool = False, version : str = "v2") -> AsyncIterator[Tuple]:
        answer_message_id = f"ai-{uuid.uuid4()}"

        # ① tasks : 노드 실행 시작 이벤트
        yield ((), "tasks", {"id" : "task-1", "name" : "agent", "input" : {"question" : "서울"}})

        # ② messages : 토큰 스트리밍 (동일 message_id 로 조각이 나뉘어 도착)
        yield ((), "messages", (AIMessageChunk(content = "서울은 ", id = answer_message_id), {"langgraph_node" : "agent"}))
        yield ((), "messages", (AIMessageChunk(content = "대한민국의 수도이며 ", id = answer_message_id), {"langgraph_node" : "agent"}))
        yield ((), "messages", (AIMessageChunk(content = "인구 약 940만 명의 도시입니다.", id = answer_message_id), {"langgraph_node" : "agent"}))

        # ③ custom : 사용자 정의 진행률 이벤트
        yield ((), "custom", {"progress_percent" : 50, "stage" : "generating"})

        # ④ values : 상태 스냅샷 — 여러 번 오지만 마지막 것만 final_output 으로 저장된다
        yield ((), "values", {"messages" : [{"role" : "ai", "content" : "서울은 대한민국의 수도이며 "}]})
        yield ((), "values", {"messages" : [{"role" : "ai", "content" : "서울은 대한민국의 수도이며 인구 약 940만 명의 도시입니다."}]})

        # ⑤ tasks : 노드 실행 종료 이벤트
        yield ((), "tasks", {"id" : "task-1", "name" : "agent", "result" : "completed"})
