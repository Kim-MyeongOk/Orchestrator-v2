##################################################
# 오케스트레이터 API 라우터
# POST /api/v1/orchestrator/stream :
# 이력 복원 → 사용자 메시지 선행 적재 → 그래프 스트리밍(SSE 실시간 yield + Redis 누적)
# → 정상 종료 순간 동일 요청 컨텍스트에서 Redis 버퍼를 llm_* 스키마로 flush 한다.
# 저장은 llm 도메인 리포지토리를 재사용하며, 컴포넌트는 server.py 조립 지점에서 생성자 주입된다.
# 신원은 llm 도메인 관례대로 X-User-Id 헤더로 받는다.
##################################################

import uuid
import asyncio

# uv add fastapi
from typing                  import Any
from typing                  import AsyncIterator
from typing                  import Dict
from typing                  import List
from datetime                import datetime
from datetime                import timezone
from fastapi                 import APIRouter
from fastapi                 import Header
from fastapi                 import HTTPException
from fastapi.responses       import StreamingResponse
from langchain_core.messages import HumanMessage

from common.identifier.uuid_v7.uuid_v7_generator      import UUIDV7Generator
from common.network.sse.sse_helper                    import SseHelper
from app.llm.job.job_manager.job_ownership_error      import JobOwnershipError
from app.orchestrator.api.orchestrator_stream_request import OrchestratorStreamRequest
from app.orchestrator.service.chat_history_service    import ChatHistoryService
from app.orchestrator.service.chunk_flush_service     import ChunkFlushService
from app.orchestrator.service.graph_stream_executor   import GraphStreamExecutor
from app.orchestrator.service.redis_chunk_buffer      import RedisChunkBuffer


class OrchestratorAPIRouter:
    def __init__(self, compiled_graph : Any, uuid_v7_generator : UUIDV7Generator, chat_history_service : ChatHistoryService, chunk_flush_service : ChunkFlushService, graph_stream_executor : GraphStreamExecutor, redis_chunk_buffer : RedisChunkBuffer, is_checkpoint_enabled : bool = False):
        # compiled_graph        : workflow.compile() 결과(CompiledStateGraph). 체크포인트 활성 시 lifespan 에서 체크포인터 주입본으로 교체된다
        # is_checkpoint_enabled : True 면 LangGraph 체크포인터가 thread_id 로 상태를 복원하므로 수동 이력 복원을 건너뛴다 (이중 주입 방지)
        self.compiled_graph        = compiled_graph
        self.uuid_v7_generator     = uuid_v7_generator
        self.chat_history_service  = chat_history_service
        self.chunk_flush_service   = chunk_flush_service
        self.graph_stream_executor = graph_stream_executor
        self.redis_chunk_buffer    = redis_chunk_buffer
        self.is_checkpoint_enabled = is_checkpoint_enabled
        self.api_router            = APIRouter(prefix = "/api/v1/orchestrator", tags = ["orchestrator"])
        self.api_router.add_api_route("/stream", self.stream_orchestrator_async, methods = ["POST"])

    async def _create_sse_stream_async(self, thread_id : uuid.UUID, run_id : uuid.UUID, user_id : uuid.UUID, input_message_list : List[Any], initial_input_dictionary : Dict[str, Any], started_at : datetime) -> AsyncIterator[str]:
        event_sequence_number = 0
        is_stream_finished    = False
        try:
            yield SseHelper.format_event(event_name = "start", data_dictionary = {"run_id" : str(run_id), "thread_id" : str(thread_id)})

            # 각 청크는 executor 내부에서 Redis 에 실시간 누적(Append)되는 동시에 SSE 로 yield 된다
            async for chunk_dictionary in self.graph_stream_executor.execute_graph_stream_async(self.compiled_graph, thread_id, run_id, input_message_list):
                event_sequence_number = event_sequence_number + 1
                yield SseHelper.format_event(event_name = str(chunk_dictionary.get("chunk_type") or "chunk"), data_dictionary = chunk_dictionary, event_id = event_sequence_number)
            is_stream_finished = True

            # 스트리밍이 예외 없이 정상 종료된 순간, 동일 요청 컨텍스트에서 즉시 flush 한다.
            # asyncio.shield : flush 도중 클라이언트가 끊겨도 저장 처리만은 끝까지 실행한다.
            await asyncio.shield(self.chunk_flush_service.flush_buffer_to_postgres_async(thread_id, run_id, user_id, initial_input_dictionary, started_at))
            yield SseHelper.format_event(event_name = "done", data_dictionary = {"run_id" : str(run_id), "status" : "completed"})
        except Exception as exception:
            # 런타임 에러 : 클라이언트에 에러 이벤트를 전송하고 스트림을 닫는다
            yield SseHelper.format_event(event_name = "error", data_dictionary = {"run_id" : str(run_id), "message" : str(exception)})
        finally:
            # 네트워크 단절(CancelledError 포함) / 스트리밍 중 에러 : 불완전 버퍼를 즉시 정리한다.
            # (flush 만 실패한 경우에는 버퍼를 보존하여 TTL 안에 복구할 여지를 남긴다)
            if not is_stream_finished:
                await asyncio.shield(self.redis_chunk_buffer.delete_buffer_async(thread_id, run_id))

    async def stream_orchestrator_async(self, stream_request : OrchestratorStreamRequest, x_user_id : uuid.UUID = Header(alias = "X-User-Id")) -> StreamingResponse:
        thread_id  = stream_request.thread_id or self.uuid_v7_generator.generate()
        run_id     = self.uuid_v7_generator.generate()
        started_at = datetime.now(timezone.utc)

        try:
            # ① 이전 대화 이력 복원 (대화 재개, 소유권은 스레드 최초 job 의 user_id 로 강제)
            #    체크포인트 활성 시 : LangGraph 체크포인터가 configurable.thread_id 로 상태를 자동 복원하므로
            #    수동 복원을 건너뛴다 (같은 이력이 두 번 주입되는 이중 저장 문제 방지).
            #    소유권 검사는 아래 store_user_message_async 내부에서 계속 수행된다.
            history_message_list = [] if self.is_checkpoint_enabled else await self.chat_history_service.get_chat_history_async(thread_id, x_user_id)

            # ② 사용자 질문을 llm_job_message 에 선행 적재한다 (thread upsert 포함 — 스트리밍 실패와 무관하게 질문은 이력에 남는다)
            #    체크포인트 활성 시에도 유지 : checkpoint_* 는 실행 상태 원본, llm_job_message 는 조회/표시용 프로젝션으로 역할이 분리된다
            await self.chunk_flush_service.store_user_message_async(thread_id, run_id, x_user_id, stream_request.user_message, stream_request.files_metadata)
        except JobOwnershipError as job_ownership_error:
            raise HTTPException(status_code = 403, detail = str(job_ownership_error))

        # ③ 복원 이력 + 신규 메시지로 그래프 입력을 구성한다
        input_message_list       = history_message_list + [HumanMessage(content = stream_request.user_message)]
        initial_input_dictionary = {"messages" : [{"role" : "human", "content" : stream_request.user_message}]}

        sse_stream = self._create_sse_stream_async(thread_id, run_id, x_user_id, input_message_list, initial_input_dictionary, started_at)
        return StreamingResponse(sse_stream, media_type = "text/event-stream", headers = {"Cache-Control" : "no-cache", "X-Accel-Buffering" : "no"})

    def get_router(self) -> APIRouter:
        return self.api_router
