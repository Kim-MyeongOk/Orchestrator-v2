##################################################
# Think-태그 병목 진단/모니터링 FastAPI 앱 (독립 실행)
# 동일 thread_id 연속 호출 시 Qwen 계열의 생각 토큰(<think>...</think> 혹은
# reasoning_content)이 체크포인트 messages 채널에 누적되어 프리필(TTFT)이
# 느려지는 병목을 측정·분석한다.
#
#   실행 : python src/think_bottleneck_monitor.py          (기본 포트 8002)
#   진단 : GET  /diagnose?thread_id=<스레드ID>
#   재현 : POST /stream   {"thread_id": "...", "message": "..."}
#
# 본 앱은 메인 서버와 같은 PostgreSQL 체크포인트 테이블을 공유하므로
# 운영 스레드를 그대로 진단할 수 있다. 단, /stream 은 이 앱의 단순 그래프로
# 체크포인트를 새로 쓰므로 운영 스레드가 아닌 테스트 thread_id 사용을 권장한다.
##################################################

import os
import re
import sys
import json
import time
import asyncio

# Windows : psycopg 비동기는 ProactorEventLoop 를 지원하지 않으므로 Selector 정책으로 전환한다
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

from dotenv             import load_dotenv
from contextlib         import asynccontextmanager
from typing             import Any
from typing             import AsyncIterator
from typing             import Dict
from typing             import List
from typing             import Optional
from fastapi                 import FastAPI
from fastapi                 import HTTPException
from fastapi.responses       import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic                import BaseModel

from langchain_core.messages           import BaseMessage
from langchain_core.messages           import HumanMessage
from langchain.agents.middleware.types import AgentMiddleware

from app.llm.agent.model_configuration import ModelConfiguration
from app.llm.agent.deep_agent_factory  import DeepAgentFactory

load_dotenv()

##################################################
# 생각 토큰 감지/트리밍 유틸리티
##################################################

# <think>...</think> 인라인 태그 (일부 서빙 조합은 생각 토큰을 content 안에 인라인으로 넣는다)
THINK_TAG_PATTERN = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def _extract_think_byte_count(message : BaseMessage) -> int:
    # 메시지 1건에서 생각 토큰이 차지하는 바이트 수를 계산한다
    # ① content 인라인 <think> 태그  ② additional_kwargs.reasoning_content (langchain-ollama 분리 저장 경로)
    think_byte_count = 0
    if isinstance(message.content, str):
        for think_text in THINK_TAG_PATTERN.findall(message.content):
            think_byte_count += len(think_text.encode("utf-8"))
    reasoning_text = (message.additional_kwargs or {}).get("reasoning_content")
    if isinstance(reasoning_text, str):
        think_byte_count += len(reasoning_text.encode("utf-8"))
    return think_byte_count


##################################################
# [병목 해결 가이드] 생각 토큰 트리밍 + 윈도잉 미들웨어
#
# 원칙 : 체크포인트(원본 상태)는 건드리지 않고, "모델에게 보내는 프롬프트"만
# 슬림하게 만든다. before_model 훅은 반환값이 체크포인트에 다시 기록되므로 쓰지 않는다 —
# awrap_model_call 은 모델 요청(ModelRequest)만 override 하고 State 는 그대로 둔다.
# 프로덕션(server.py 의 DeepAgentFactory.create)에도 middleware_list 로 그대로 주입 가능하다.
##################################################

def prepare_model_input(message_list : List[BaseMessage], window_message_count : int = 20) -> List[BaseMessage]:
    # ① 트리밍 : 과거 메시지의 <think> 인라인 태그와 reasoning_content 를 제거한다
    # ② 윈도잉 : 최근 N개 메시지만 유지해 프리필 상한을 고정한다 (오래된 대화는 프롬프트에서 제외)
    slim_message_list = []
    for message in message_list[-window_message_count:]:
        updated_fields : Dict[str, Any] = {}
        if isinstance(message.content, str) and "<think>" in message.content:
            updated_fields["content"] = THINK_TAG_PATTERN.sub("", message.content).strip()
        if (message.additional_kwargs or {}).get("reasoning_content"):
            updated_fields["additional_kwargs"] = {key : value for key, value in message.additional_kwargs.items() if key != "reasoning_content"}
        slim_message_list.append(message.model_copy(update = updated_fields) if updated_fields else message)
    return slim_message_list


class ThinkTrimmingMiddleware(AgentMiddleware):
    # 모델 호출 직전에만 트리밍+윈도잉을 적용한다 (체크포인트 원본 보존)
    def __init__(self, window_message_count : int = 20) -> None:
        super().__init__()
        self.window_message_count = window_message_count

    async def awrap_model_call(self, request, handler):
        slim_message_list = prepare_model_input(request.messages, self.window_message_count)
        return await handler(request.override(messages = slim_message_list))


##################################################
# LangGraph 그래프
# 운영과 동일한 deepagents 그래프를 사용한다 — 같은 체크포인트를 같은 방식으로 읽어야
# 진단(aget_state)이 운영 복원 경로를 정확히 재현한다. (단순 MessagesState 그래프는
# deepagents 체크포인트의 pending writes 를 적용하지 못해 messages 가 0 으로 보인다)
##################################################

def _create_compiled_graph(checkpoint_saver, model_name : Optional[str] = None):
    # model_name : 요청별 모델 선택 (None 이면 .env 기본 모델)
    model_configuration = ModelConfiguration(
        provider            = os.getenv("MODEL_PROVIDER", "ollama"),
        model_name          = model_name or os.getenv("MODEL_NAME", "qwen3-vl:4b"),
        base_url            = os.getenv("MODEL_BASE_URL", "http://localhost:11434"),
        reasoning_enabled   = False,  # think 파라미터 지원 모델에서는 생각 토큰 생성을 원천 차단 (thinking 전용 변형은 무시함)
        context_token_count = int(os.getenv("MODEL_CONTEXT_TOKEN_COUNT", "8192")),   # Ollama 기본 4096 은 deepagents 프롬프트+히스토리에 부족 → 절단 → thinking 폭주
        maximum_token_count = int(os.getenv("MODEL_MAXIMUM_TOKEN_COUNT", "4096") or "4096")   # 폭주 시 생성 상한 (thinking 포함)
    )
    return DeepAgentFactory.create(
        model_configuration,
        checkpointer    = checkpoint_saver,
        middleware_list = [ThinkTrimmingMiddleware()]   # [병목 해결 가이드] 실제 적용 상태
    )


##################################################
# FastAPI 애플리케이션
##################################################

class StreamRequest(BaseModel):
    thread_id : str
    message   : str
    model     : Optional[str] = None   # 요청별 모델 선택 (미지정 시 .env 기본 모델)


class MonitorApplication:
    def __init__(self) -> None:
        self.checkpoint_saver           = None
        self.checkpoint_connection_pool = None
        self.compiled_graph_dictionary  = {}   # 모델명 → 컴파일 그래프 캐시 (요청별 모델 선택 지원, 체크포인터 공유)
        self.application               = FastAPI(title = "Think Bottleneck Monitor", lifespan = self._lifespan_async)
        # 로컬 진단 대시보드(frontend/index.html 을 file:// 로 직접 오픈)에서의 fetch 를 허용한다
        self.application.add_middleware(CORSMiddleware, allow_origins = ["*"], allow_methods = ["*"], allow_headers = ["*"])
        self.application.add_api_route("/diagnose", self.diagnose_thread_async, methods = ["GET"])
        self.application.add_api_route("/models",   self.list_models_async,     methods = ["GET"])
        self.application.add_api_route("/stream",   self.stream_async,          methods = ["POST"])

    def _get_or_create_compiled_graph(self, model_name : Optional[str]):
        # 모델별 그래프를 지연 생성해 캐싱한다 (같은 체크포인터를 공유하므로 스레드 이력은 모델과 무관하게 이어진다)
        cache_key = model_name or os.getenv("MODEL_NAME", "qwen3-vl:4b")
        if cache_key not in self.compiled_graph_dictionary:
            self.compiled_graph_dictionary[cache_key] = _create_compiled_graph(self.checkpoint_saver, cache_key)
        return self.compiled_graph_dictionary[cache_key]

    async def list_models_async(self) -> Dict[str, Any]:
        # Ollama 에 설치된 모델 목록을 프록시한다 (프론트 모델 선택 드롭다운용)
        import httpx
        ollama_base_url = os.getenv("MODEL_BASE_URL", "http://localhost:11434")
        try:
            async with httpx.AsyncClient(timeout = 5.0) as http_client:
                response = await http_client.get(f"{ollama_base_url}/api/tags")
                response.raise_for_status()
                model_name_list = [model_entry["name"] for model_entry in response.json().get("models", [])]
        except Exception as exception:
            raise HTTPException(status_code = 502, detail = f"OLLAMA MODEL LIST FAILED : {exception}")
        return {"default_model" : os.getenv("MODEL_NAME", "qwen3-vl:4b"), "models" : model_name_list}

    @asynccontextmanager
    async def _lifespan_async(self, application : FastAPI) -> AsyncIterator[None]:
        # PostgreSQL 체크포인터 (메인 서버와 동일 테이블 공유 → 운영 스레드 진단 가능)
        # 임시 테스트용 InMemorySaver 로 바꾸려면 아래 3줄 대신 :
        #   from langgraph.checkpoint.memory import InMemorySaver
        #   checkpoint_saver = InMemorySaver()
        from psycopg.rows                      import dict_row
        from psycopg_pool                      import AsyncConnectionPool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        connection_info_text = (
            f"host={os.getenv('POSTGRESQL_HOST', 'localhost')} "
            f"port={os.getenv('POSTGRESQL_PORT', '5432')} "
            f"dbname={os.getenv('POSTGRESQL_DATABASE', 'postgres')} "
            f"user={os.getenv('POSTGRESQL_USER', 'postgres')} "
            f"password={os.getenv('POSTGRESQL_PASSWORD', 'postgres')}"
        )
        self.checkpoint_connection_pool = AsyncConnectionPool(connection_info_text, min_size = 1, max_size = 3, open = False, kwargs = {"autocommit" : True, "row_factory" : dict_row})
        await self.checkpoint_connection_pool.open()
        checkpoint_saver = AsyncPostgresSaver(self.checkpoint_connection_pool)
        await checkpoint_saver.setup()

        self.checkpoint_saver = checkpoint_saver
        self._get_or_create_compiled_graph(None)   # 기본 모델 그래프 선생성
        try:
            yield
        finally:
            await self.checkpoint_connection_pool.close()

    async def diagnose_thread_async(self, thread_id : str) -> Dict[str, Any]:
        # ① 순수 체크포인트 로드 시간 : aget_state 전후를 perf_counter 로 측정한다
        runnable_configuration = {"configurable" : {"thread_id" : thread_id}}
        load_started_at        = time.perf_counter()
        state_snapshot         = await self._get_or_create_compiled_graph(None).aget_state(runnable_configuration)
        load_time_ms           = (time.perf_counter() - load_started_at) * 1000

        message_list : List[BaseMessage] = state_snapshot.values.get("messages", []) if state_snapshot else []
        if not message_list and (state_snapshot is None or not state_snapshot.values):
            raise HTTPException(status_code = 404, detail = f"NO CHECKPOINT STATE : {thread_id}")

        # ② 메시지 수  ③ 생각 토큰 총 바이트(KB) — 인라인 <think> + reasoning_content 합산
        think_total_byte_count = sum(_extract_think_byte_count(message) for message in message_list)
        return {
            "load_time_ms"  : round(load_time_ms, 1),
            "message_count" : len(message_list),
            "think_tag_kb"  : round(think_total_byte_count / 1024, 1)
        }

    async def stream_async(self, stream_request : StreamRequest) -> StreamingResponse:
        runnable_configuration = {"configurable" : {"thread_id" : stream_request.thread_id}}
        input_dictionary       = {"messages" : [HumanMessage(content = stream_request.message)]}
        compiled_graph         = self._get_or_create_compiled_graph(stream_request.model)

        async def generate_token_stream_async() -> AsyncIterator[str]:
            request_started_at   = time.perf_counter()
            is_first_token_seen  = False
            print(f"STREAM START : THREAD {stream_request.thread_id} - MODEL {stream_request.model or os.getenv('MODEL_NAME', 'qwen3-vl:4b')}", flush = True)
            async for message_chunk, _metadata in compiled_graph.astream(input_dictionary, runnable_configuration, stream_mode = "messages"):
                token_text = message_chunk.content if isinstance(message_chunk.content, str) else ""
                if not token_text:
                    continue
                if not is_first_token_seen:
                    is_first_token_seen = True
                    # TTFT(Time To First Token) : 프리필 병목이 여기 숫자로 그대로 드러난다
                    print(f"TTFT : THREAD {stream_request.thread_id} - {(time.perf_counter() - request_started_at) * 1000:.0f}ms", flush = True)
                yield token_text
            print(f"TURN COMPLETED : THREAD {stream_request.thread_id} - TOTAL {(time.perf_counter() - request_started_at) * 1000:.0f}ms", flush = True)

        return StreamingResponse(generate_token_stream_async(), media_type = "text/plain; charset=utf-8", headers = {"Cache-Control" : "no-cache", "X-Accel-Buffering" : "no"})

    def get_application(self) -> FastAPI:
        return self.application


if __name__ == "__main__":
    monitor_application = MonitorApplication()
    uvicorn_config      = uvicorn.Config(monitor_application.get_application(), host = os.getenv("MONITOR_HOST", "localhost"), port = int(os.getenv("MONITOR_PORT", "8002")))
    uvicorn_server      = uvicorn.Server(uvicorn_config)
    if sys.platform == "win32":
        asyncio.run(uvicorn_server.serve(), loop_factory = asyncio.SelectorEventLoop)
    else:
        uvicorn_server.run()
