##################################################
# 그래프 스트림 실행기
# LangGraph astream(stream_mode=["tasks","messages","values","custom"], subgraphs=True, version="v2")
# 을 실행하며 청크를 Redis 에 실시간 누적하고, 스트리밍이 완전히 완료되면
# Redis 버퍼를 병합 규칙에 따라 PostgreSQL 로 flush 한다.
##################################################

from typing import Any
from typing import AsyncIterator
from typing import Dict
from typing import List
from typing import Optional

from app.orchestrator.service.chunk_flush_service    import ChunkFlushService
from app.orchestrator.service.chunk_serialize_helper import ChunkSerializeHelper
from app.orchestrator.service.redis_chunk_buffer     import RedisChunkBuffer


class GraphStreamExecutor:
    def __init__(self, redis_chunk_buffer : RedisChunkBuffer, chunk_flush_service : ChunkFlushService):
        self.redis_chunk_buffer  = redis_chunk_buffer
        self.chunk_flush_service = chunk_flush_service

    async def execute_graph_stream_async(self, compiled_graph : Any, thread_id : str, run_id : str, input_message_list : List[Any], initial_input_dictionary : Dict[str, Any], user_message_dictionary : Optional[Dict[str, Any]] = None) -> AsyncIterator[Dict[str, Any]]:
        runnable_configuration = {"configurable" : {"thread_id" : thread_id, "run_id" : run_id}}

        # input_message_list 에는 이미 복원된 이전 이력 + 이번 사용자 메시지가 들어 있어야 한다
        async for stream_chunk in compiled_graph.astream({"messages" : input_message_list}, runnable_configuration, stream_mode = ["tasks", "messages", "values", "custom"], subgraphs = True, version = "v2"):
            chunk_dictionary = ChunkSerializeHelper.create_chunk_dictionary(stream_chunk)
            if chunk_dictionary is None:
                continue
            # 원본/변환 청크를 Redis 에 실시간 누적한 뒤 호출자에게 그대로 흘린다 (SSE 전송 등)
            await self.redis_chunk_buffer.append_chunk_async(thread_id, run_id, chunk_dictionary)
            yield chunk_dictionary

        # 스트리밍이 예외 없이 '완전히' 종료된 시점에만 PostgreSQL 로 flush 한다.
        # 중간 실패 run 의 버퍼는 Redis TTL 로 자동 정리되며, 필요 시 별도 복구 로직에서 재사용할 수 있다.
        await self.chunk_flush_service.flush_buffer_to_postgres_async(thread_id, run_id, initial_input_dictionary, user_message_dictionary)
