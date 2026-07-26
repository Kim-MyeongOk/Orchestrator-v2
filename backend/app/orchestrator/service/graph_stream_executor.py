##################################################
# 그래프 스트림 실행기
# LangGraph astream(stream_mode=["tasks","messages","values","custom"], subgraphs=True, version="v2")
# 을 실행하며 청크를 Redis 에 실시간 누적(Append)하고 호출자에게 그대로 흘린다.
# flush 는 호출자(API 라우터 / 데모)가 스트림 정상 종료 시점에 ChunkFlushService 로 직접 수행한다.
##################################################

import uuid

from typing import Any
from typing import AsyncIterator
from typing import Dict
from typing import List

from app.orchestrator.service.chunk_serialize_helper import ChunkSerializeHelper
from app.orchestrator.service.redis_chunk_buffer     import RedisChunkBuffer


class GraphStreamExecutor:
    def __init__(self, redis_chunk_buffer : RedisChunkBuffer):
        self.redis_chunk_buffer = redis_chunk_buffer

    async def execute_graph_stream_async(self, compiled_graph : Any, thread_id : uuid.UUID, run_id : uuid.UUID, input_message_list : List[Any]) -> AsyncIterator[Dict[str, Any]]:
        runnable_configuration = {"configurable" : {"thread_id" : str(thread_id), "run_id" : str(run_id)}}

        # input_message_list 에는 이미 복원된 이전 이력 + 이번 사용자 메시지가 들어 있어야 한다
        async for stream_chunk in compiled_graph.astream({"messages" : input_message_list}, runnable_configuration, stream_mode = ["tasks", "messages", "values", "custom"], subgraphs = True, version = "v2"):
            chunk_dictionary = ChunkSerializeHelper.create_chunk_dictionary(stream_chunk)
            if chunk_dictionary is None:
                continue
            # 원본/변환 청크를 Redis 에 실시간 누적한 뒤 호출자에게 그대로 흘린다 (SSE 전송 등)
            await self.redis_chunk_buffer.append_chunk_async(thread_id, run_id, chunk_dictionary)
            yield chunk_dictionary
