##################################################
# 그래프 스트림 실행기 데모
# 가상의 LangGraph 컴파일 객체(app = workflow.compile() 을 흉내 낸 FakeCompiledGraph)로
# [이력 조회 → 스트리밍 → Redis 누적 → 청크 병합 → PostgreSQL flush → 이력 재조회]
# 전체 파이프라인을 실행한다.
#
# 실행 : cd src && uv run app/orchestrator/service/demo_graph_stream_executor.py
##################################################

import asyncio
import uuid

# uv add langchain-core
from typing                  import Any
from typing                  import AsyncIterator
from typing                  import Dict
from typing                  import List
from typing                  import Tuple
from langchain_core.messages import AIMessageChunk
from langchain_core.messages import HumanMessage
from redis.asyncio           import Redis

from common.database.sqlalchemy_async.sqlalchemy_engine_manager import SqlalchemyEngineManager
from app.orchestrator.model.orchestrator_base                   import OrchestratorBase
from app.orchestrator.service.chat_history_service              import ChatHistoryService
from app.orchestrator.service.chunk_flush_service               import ChunkFlushService
from app.orchestrator.service.graph_stream_executor             import GraphStreamExecutor
from app.orchestrator.service.redis_chunk_buffer                import RedisChunkBuffer


class FakeCompiledGraph:
    # workflow.compile() 결과(CompiledStateGraph)를 흉내 낸다. astream 시그니처 동일.
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


async def main_async() -> None:
    # 1. 인프라 연결 (PostgreSQL + Redis)
    engine_manager = SqlalchemyEngineManager(database_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres")
    engine_manager.open()
    async with engine_manager.async_engine.begin() as connection:
        await connection.run_sync(OrchestratorBase.metadata.create_all)
    redis_client = Redis(host = "localhost", port = 6379, db = 0, decode_responses = True)

    # 2. 컴포넌트 조립 (server.py 의 조립 지점과 동일한 방식)
    redis_chunk_buffer    = RedisChunkBuffer(redis_client = redis_client)
    chunk_flush_service   = ChunkFlushService(async_session_factory = engine_manager.async_session_factory, redis_chunk_buffer = redis_chunk_buffer)
    chat_history_service  = ChatHistoryService(async_session_factory = engine_manager.async_session_factory)
    graph_stream_executor = GraphStreamExecutor(redis_chunk_buffer = redis_chunk_buffer, chunk_flush_service = chunk_flush_service)

    thread_id            = "thread-demo-0001"
    run_id               = f"run-{uuid.uuid4()}"
    user_message_content = "서울에 대해 알려줘"

    print("-" * 50)
    print("STEP 1 : RESTORE CHAT HISTORY")
    # 대화 재개 : thread_id 만으로 이전 이력을 BaseMessage 목록으로 복원한다
    history_message_list = await chat_history_service.get_chat_history_async(thread_id)
    print(f"RESTORED HISTORY MESSAGE COUNT : {len(history_message_list)}")

    print("-" * 50)
    print("STEP 2 : EXECUTE GRAPH STREAM")
    fake_compiled_graph      = FakeCompiledGraph()
    input_message_list       = history_message_list + [HumanMessage(content = user_message_content)]
    initial_input_dictionary = {"messages" : [{"role" : "human", "content" : user_message_content}]}
    user_message_dictionary  = {"content" : user_message_content, "files_metadata" : None}

    async for chunk_dictionary in graph_stream_executor.execute_graph_stream_async(fake_compiled_graph, thread_id, run_id, input_message_list, initial_input_dictionary, user_message_dictionary):
        chunk_preview = str(chunk_dictionary.get("content") if chunk_dictionary.get("chunk_type") == "messages" else chunk_dictionary.get("payload"))[:60]
        print(f"STREAM CHUNK : {chunk_dictionary['chunk_type']} - {chunk_preview}")

    print("-" * 50)
    print("STEP 3 : VERIFY FLUSH RESULT")
    # flush 후 다시 조회 : 사용자 메시지 1개 + 병합 완료된 AI 메시지 1개가 늘어나 있어야 한다
    restored_message_list = await chat_history_service.get_chat_history_async(thread_id)
    print(f"MESSAGE COUNT AFTER FLUSH : {len(restored_message_list)}")
    for restored_message in restored_message_list:
        print(f"RESTORED MESSAGE : {restored_message.type} - {str(restored_message.content)[:60]}")

    # 3. 정리
    await redis_client.aclose()
    await engine_manager.close_async()


if __name__ == "__main__":
    asyncio.run(main_async())
