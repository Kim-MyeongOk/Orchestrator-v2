##################################################
# 그래프 스트림 실행기 데모
# 가상의 LangGraph 컴파일 객체(FakeCompiledGraph)로
# [이력 조회 → 사용자 메시지 선행 적재 → 스트리밍 → Redis 누적 → 청크 병합
#  → llm_* 스키마 flush(리포지토리 재사용) → 이력 재조회] 전체 파이프라인을 실행한다.
#
# 실행 : cd src && uv run app/orchestrator/service/demo_graph_stream_executor.py
##################################################

import asyncio
import uuid

# uv add langchain-core
from datetime                import datetime
from datetime                import timezone
from langchain_core.messages import HumanMessage
from redis.asyncio           import Redis

from common.database.postgresql.postgresql_configuration import PostgresqlConfiguration
from common.database.postgresql.postgresql_pool_manager  import PostgresqlPoolManager
from common.identifier.uuid_v7.uuid_v7_generator         import UUIDV7Generator
from app.llm.repository.chat_thread_repository           import ChatThreadRepository
from app.llm.repository.job_message_repository           import JobMessageRepository
from app.llm.repository.job_repository                   import JobRepository
from app.llm.repository.job_schema_initializer           import JobSchemaInitializer
from app.orchestrator.agent.fake_compiled_graph          import FakeCompiledGraph
from app.orchestrator.service.chat_history_service       import ChatHistoryService
from app.orchestrator.service.chunk_flush_service        import ChunkFlushService
from app.orchestrator.service.graph_stream_executor      import GraphStreamExecutor
from app.orchestrator.service.redis_chunk_buffer         import RedisChunkBuffer


async def main_async() -> None:
    # 1. 인프라 연결 (PostgreSQL 풀 + 스키마 초기화 + Redis)
    postgresql_pool_manager = PostgresqlPoolManager(PostgresqlConfiguration(host = "localhost", port = 5432, database_name = "postgres", user_name = "postgres", password = "postgres", minimum_connection_count = 1, maximum_connection_count = 10))
    await postgresql_pool_manager.open_async()
    await JobSchemaInitializer(postgresql_pool_manager).initialize_schema_async()
    redis_client = Redis(host = "localhost", port = 6379, db = 0, decode_responses = True)

    # 2. 컴포넌트 조립 (server.py 의 조립 지점과 동일한 방식 — llm 리포지토리 재사용)
    uuid_v7_generator      = UUIDV7Generator()
    job_repository         = JobRepository(postgresql_pool_manager)
    job_message_repository = JobMessageRepository(postgresql_pool_manager)
    chat_thread_repository = ChatThreadRepository(postgresql_pool_manager)
    redis_chunk_buffer     = RedisChunkBuffer(redis_client = redis_client)
    chunk_flush_service    = ChunkFlushService(postgresql_pool_manager, redis_chunk_buffer, job_repository, job_message_repository, chat_thread_repository)
    chat_history_service   = ChatHistoryService(job_repository, job_message_repository)
    graph_stream_executor  = GraphStreamExecutor(redis_chunk_buffer = redis_chunk_buffer)

    thread_id            = uuid.UUID("01900000-0000-7000-8000-00000000d001")  # 데모 고정 스레드 (재실행 시 대화 재개 확인용)
    user_id              = uuid.UUID("01900000-0000-7000-8000-000000000001")
    run_id               = uuid_v7_generator.generate()
    started_at           = datetime.now(timezone.utc)
    user_message_content = "서울에 대해 알려줘"

    print("-" * 50)
    print("STEP 1 : RESTORE CHAT HISTORY")
    # 대화 재개 : thread_id 만으로 이전 이력을 BaseMessage 목록으로 복원한다
    history_message_list = await chat_history_service.get_chat_history_async(thread_id, user_id)
    print(f"RESTORED HISTORY MESSAGE COUNT : {len(history_message_list)}")

    print("-" * 50)
    print("STEP 2 : STORE USER MESSAGE + EXECUTE GRAPH STREAM")
    # 사용자 질문 선행 적재 (thread upsert + 소유권 검사 포함)
    await chunk_flush_service.store_user_message_async(thread_id, run_id, user_id, user_message_content, None)

    fake_compiled_graph      = FakeCompiledGraph()
    input_message_list       = history_message_list + [HumanMessage(content = user_message_content)]
    initial_input_dictionary = {"messages" : [{"role" : "human", "content" : user_message_content}]}

    async for chunk_dictionary in graph_stream_executor.execute_graph_stream_async(fake_compiled_graph, thread_id, run_id, input_message_list):
        chunk_preview = str(chunk_dictionary.get("content") if chunk_dictionary.get("chunk_type") == "messages" else chunk_dictionary.get("payload"))[:60]
        print(f"STREAM CHUNK : {chunk_dictionary['chunk_type']} - {chunk_preview}")

    # 스트리밍이 예외 없이 정상 종료된 시점에 호출자가 직접 flush 한다
    await chunk_flush_service.flush_buffer_to_postgres_async(thread_id, run_id, user_id, initial_input_dictionary, started_at)

    print("-" * 50)
    print("STEP 3 : VERIFY FLUSH RESULT")
    # flush 후 다시 조회 : 사용자 메시지 1개 + 병합 완료된 AI 메시지 1개가 늘어나 있어야 한다
    restored_message_list = await chat_history_service.get_chat_history_async(thread_id, user_id)
    print(f"MESSAGE COUNT AFTER FLUSH : {len(restored_message_list)}")
    for restored_message in restored_message_list:
        print(f"RESTORED MESSAGE : {restored_message.type} - {str(restored_message.content)[:60]}")

    # 3. 정리
    await redis_client.aclose()
    await postgresql_pool_manager.close_async()


if __name__ == "__main__":
    asyncio.run(main_async())
