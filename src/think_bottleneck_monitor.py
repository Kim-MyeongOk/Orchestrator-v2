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
from fastapi.responses       import FileResponse
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
        if isinstance(message.content, list) and any(isinstance(content_block, dict) and content_block.get("type") == "thinking" for content_block in message.content):
            # google(Gemini) : content 리스트 안의 thinking 블록 제거
            updated_fields["content"] = [content_block for content_block in message.content if not (isinstance(content_block, dict) and content_block.get("type") == "thinking")]
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

def _create_compiled_graph(checkpoint_saver, model_name : Optional[str] = None, reasoning_effort : Optional[str] = None):
    # model_name       : 요청별 모델 선택 (None 이면 .env 기본 모델)
    # reasoning_effort : 생각 강도 low|medium|high (google → thinking_budget, ollama → think 레벨)
    model_provider = os.getenv("MODEL_PROVIDER", "ollama").strip().lower()
    model_configuration = ModelConfiguration(
        provider            = model_provider,
        model_name          = model_name or os.getenv("MODEL_NAME", "qwen3-vl:4b"),
        api_key             = os.getenv("MODEL_API_KEY") or None,
        base_url            = os.getenv("MODEL_BASE_URL") or None,
        reasoning_enabled   = True,   # True : thinking 을 분리 수신(ollama: reasoning_content / google: include_thoughts) → 실시간 UI 표시 가능
                                      # (다음 턴 프롬프트에서는 ThinkTrimmingMiddleware 가 제거하므로 컨텍스트를 오염시키지 않는다)
        reasoning_effort    = reasoning_effort,
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

def _extract_message_texts(message : BaseMessage) -> tuple:
    # 저장 메시지 1건에서 (본문 텍스트, 생각 텍스트) 를 추출한다
    # ollama 는 additional_kwargs.reasoning_content, google(Gemini) 은 content 리스트의 thinking 블록
    reasoning_text = (getattr(message, "additional_kwargs", None) or {}).get("reasoning_content", "") or ""
    body_text      = ""
    if isinstance(message.content, str):
        body_text = message.content
    elif isinstance(message.content, list):
        for content_block in message.content:
            if isinstance(content_block, str):
                body_text += content_block
            elif isinstance(content_block, dict):
                if content_block.get("type") == "thinking":
                    reasoning_text += content_block.get("thinking", "")
                elif content_block.get("type") == "text":
                    body_text += content_block.get("text", "")
    return body_text.strip(), reasoning_text


class RoomUpsertRequest(BaseModel):
    user_id          : str
    room_id          : str
    thread_id        : str
    title            : str            = "새 대화"
    model            : Optional[str]  = None
    reasoning_effort : Optional[str]  = None


class StreamRequest(BaseModel):
    thread_id         : str
    message           : str
    model             : Optional[str] = None    # 요청별 모델 선택 (미지정 시 .env 기본 모델)
    reasoning_effort  : Optional[str] = None    # 생각 강도 : low | medium | high | None(모델 기본)
    include_reasoning : bool          = False   # True : NDJSON 이벤트 스트림({"type":"reasoning"|"token","text":...}) 으로 생각 과정을 함께 전송
                                                # False : 답변 토큰만 평문 스트림 (기존 클라이언트 하위호환)


class MonitorApplication:
    def __init__(self) -> None:
        self.checkpoint_saver           = None
        self.checkpoint_connection_pool = None
        self.compiled_graph_dictionary  = {}   # 모델명 → 컴파일 그래프 캐시 (요청별 모델 선택 지원, 체크포인터 공유)
        self.application               = FastAPI(title = "Think Bottleneck Monitor", lifespan = self._lifespan_async)
        # 로컬 진단 대시보드(frontend/index.html 을 file:// 로 직접 오픈)에서의 fetch 를 허용한다
        self.application.add_middleware(CORSMiddleware, allow_origins = ["*"], allow_methods = ["*"], allow_headers = ["*"])
        self.application.add_api_route("/diagnose",                    self.diagnose_thread_async,    methods = ["GET"])
        self.application.add_api_route("/models",                      self.list_models_async,        methods = ["GET"])
        self.application.add_api_route("/stream",                      self.stream_async,             methods = ["POST"])
        # 유저별 채팅방 목록 영속화 : 목록/메타는 chat_room 테이블, 대화 내용은 LangGraph 체크포인트에서 복원
        self.application.add_api_route("/rooms",                       self.list_rooms_async,         methods = ["GET"])
        self.application.add_api_route("/rooms",                       self.upsert_room_async,        methods = ["POST"])
        self.application.add_api_route("/rooms/{room_id}",             self.delete_room_async,        methods = ["DELETE"])
        self.application.add_api_route("/threads/{thread_id}/messages", self.get_thread_messages_async, methods = ["GET"])
        self.application.add_api_route("/redis/{thread_id}",           self.get_redis_snapshot_async,  methods = ["GET"])   # 디버그 패널용 Redis 캐시 조회
        self.application.add_api_route("/dev/api-client",              self.get_api_client_page_async, methods = ["GET"], include_in_schema = False)   # APIDog 스타일 API 테스트 페이지 (디버그 패널 [API 테스트] 버튼)
        self.redis_client = None   # 지연 생성 (디버그 패널에서 처음 조회할 때 연결)

    def _get_or_create_compiled_graph(self, model_name : Optional[str], reasoning_effort : Optional[str] = None):
        # (모델, 생각 강도)별 그래프를 지연 생성해 캐싱한다 (같은 체크포인터를 공유하므로 스레드 이력은 설정과 무관하게 이어진다)
        cache_key = (model_name or os.getenv("MODEL_NAME", "qwen3-vl:4b"), reasoning_effort)
        if cache_key not in self.compiled_graph_dictionary:
            self.compiled_graph_dictionary[cache_key] = _create_compiled_graph(self.checkpoint_saver, cache_key[0], cache_key[1])
        return self.compiled_graph_dictionary[cache_key]

    async def list_models_async(self) -> Dict[str, Any]:
        # 프론트 모델 선택 드롭다운용 : ollama 는 설치 모델을 프록시, 그 외 프로바이더는 기본 모델만 노출한다
        default_model  = os.getenv("MODEL_NAME", "qwen3-vl:4b")
        model_provider = os.getenv("MODEL_PROVIDER", "ollama").strip().lower()
        if model_provider != "ollama":
            return {"default_model" : default_model, "models" : [default_model], "provider" : model_provider}
        import httpx
        ollama_base_url = os.getenv("MODEL_BASE_URL", "http://localhost:11434")
        try:
            async with httpx.AsyncClient(timeout = 5.0) as http_client:
                response = await http_client.get(f"{ollama_base_url}/api/tags")
                response.raise_for_status()
                model_name_list = [model_entry["name"] for model_entry in response.json().get("models", [])]
        except Exception as exception:
            raise HTTPException(status_code = 502, detail = f"OLLAMA MODEL LIST FAILED : {exception}")
        return {"default_model" : default_model, "models" : model_name_list, "provider" : model_provider}

    @staticmethod
    async def _apply_checkpoint_migrations_async(checkpoint_connection_pool) -> None:
        # AsyncPostgresSaver.setup() 대체 : checkpoints 계열이 파티션 테이블인 환경에서는 setup() 의
        # CREATE INDEX CONCURRENTLY 마이그레이션이 PostgreSQL 제약으로 크래시하므로, 미적용 마이그레이션만
        # 일반 CREATE INDEX 로 치환해 순서대로 적용하고 적용 버전을 checkpoint_migrations 에 기록한다
        from langgraph.checkpoint.postgres.base import MIGRATIONS
        async with checkpoint_connection_pool.connection() as connection:
            await connection.execute("CREATE TABLE IF NOT EXISTS checkpoint_migrations (v INTEGER PRIMARY KEY)")
            cursor              = await connection.execute("SELECT v FROM checkpoint_migrations")
            applied_version_set = {version_row["v"] for version_row in await cursor.fetchall()}
            for migration_version, migration_sql in enumerate(MIGRATIONS):
                if migration_version in applied_version_set:
                    continue
                await connection.execute(migration_sql.replace("CREATE INDEX CONCURRENTLY", "CREATE INDEX"))
                await connection.execute("INSERT INTO checkpoint_migrations (v) VALUES (%s) ON CONFLICT (v) DO NOTHING", (migration_version,))
                print(f"CHECKPOINT MIGRATION APPLIED : VERSION {migration_version}", flush = True)

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
        # setup() 직접 호출 금지 : 파티션 테이블 환경에서 CONCURRENTLY 인덱스 마이그레이션이 크래시한다 (위 헬퍼로 동등 적용)
        await MonitorApplication._apply_checkpoint_migrations_async(self.checkpoint_connection_pool)

        self.checkpoint_saver = checkpoint_saver
        self._get_or_create_compiled_graph(None)   # 기본 모델 그래프 선생성

        # 유저별 채팅방 목록 테이블 (대화 내용은 체크포인트가 원본이므로 여기는 목록/메타만 저장)
        async with self.checkpoint_connection_pool.connection() as connection:
            await connection.execute("""
CREATE TABLE IF NOT EXISTS chat_room
(
    room_id          TEXT        PRIMARY KEY,
    user_id          TEXT        NOT NULL,
    thread_id        TEXT        NOT NULL,
    title            TEXT        NOT NULL DEFAULT '새 대화',
    model            TEXT,
    reasoning_effort TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_room_user_updated ON chat_room (user_id, updated_at DESC);
""")
        try:
            yield
        finally:
            await self.checkpoint_connection_pool.close()

    async def list_rooms_async(self, user_id : str) -> Dict[str, Any]:
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT room_id, thread_id, title, model, reasoning_effort FROM chat_room WHERE user_id = %s ORDER BY updated_at DESC", (user_id,))
            room_row_list = await cursor.fetchall()
        return {"rooms" : [dict(room_row) for room_row in room_row_list]}

    async def upsert_room_async(self, room_request : RoomUpsertRequest) -> Dict[str, Any]:
        async with self.checkpoint_connection_pool.connection() as connection:
            await connection.execute(
                "INSERT INTO chat_room (room_id, user_id, thread_id, title, model, reasoning_effort) VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (room_id) DO UPDATE SET thread_id = EXCLUDED.thread_id, title = EXCLUDED.title, model = EXCLUDED.model, "
                "reasoning_effort = EXCLUDED.reasoning_effort, updated_at = NOW()",
                (room_request.room_id, room_request.user_id, room_request.thread_id, room_request.title, room_request.model, room_request.reasoning_effort))
        return {"status" : "ok"}

    async def delete_room_async(self, room_id : str, user_id : str) -> Dict[str, Any]:
        # 목록에서만 제거한다 (체크포인트 대화 원본은 retention 배치가 유휴 기준으로 정리)
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute("DELETE FROM chat_room WHERE room_id = %s AND user_id = %s", (room_id, user_id))
            if cursor.rowcount == 0:
                raise HTTPException(status_code = 404, detail = f"ROOM NOT FOUND : {room_id}")
        return {"status" : "deleted"}

    async def get_api_client_page_async(self) -> FileResponse:
        # 새 창(/dev/api-client)으로 여는 API 테스트 페이지 : 백엔드가 직접 서빙하므로 origin = API 베이스 (CORS 불필요)
        frontend_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "api_client.html")
        if not os.path.isfile(frontend_file_path):
            raise HTTPException(status_code = 404, detail = f"API CLIENT PAGE NOT FOUND : {frontend_file_path}")
        return FileResponse(frontend_file_path, media_type = "text/html")

    async def get_redis_snapshot_async(self, thread_id : str) -> Dict[str, Any]:
        # 디버그 패널용 : 해당 스레드와 관련된 Redis 키를 실시간 스냅샷으로 반환한다
        # (오케스트레이터 파이프라인의 청크 버퍼 키 형식 : orch:{thread_id}:run:{run_id}:chunk_list)
        import redis.asyncio as redis_asyncio
        if self.redis_client is None:
            self.redis_client = redis_asyncio.Redis(
                host = os.getenv("REDIS_HOST", "localhost"),
                port = int(os.getenv("REDIS_PORT", "6379")),
                db   = int(os.getenv("REDIS_DATABASE_INDEX", "0"))
            )
        def try_parse_json(raw_value):
            text = raw_value.decode("utf-8", errors = "replace") if isinstance(raw_value, bytes) else str(raw_value)
            try:
                return json.loads(text)
            except Exception:
                return text
        try:
            matched_key_list = []
            async for key_bytes in self.redis_client.scan_iter(match = f"*{thread_id}*", count = 200):
                matched_key_list.append(key_bytes.decode("utf-8", errors = "replace"))
                if len(matched_key_list) >= 50:   # 디버그 표시용 상한
                    break
            key_snapshot_list = []
            for key_name in sorted(matched_key_list):
                key_type = (await self.redis_client.type(key_name)).decode()
                ttl_second_count = await self.redis_client.ttl(key_name)
                if key_type == "list":
                    total_length = await self.redis_client.llen(key_name)
                    value = [try_parse_json(item) for item in await self.redis_client.lrange(key_name, -30, -1)]   # 최근 30개만
                elif key_type == "hash":
                    total_length = await self.redis_client.hlen(key_name)
                    value = {field.decode("utf-8", "replace") : try_parse_json(item) for field, item in (await self.redis_client.hgetall(key_name)).items()}
                elif key_type == "string":
                    total_length = 1
                    value = try_parse_json(await self.redis_client.get(key_name))
                else:
                    total_length = None
                    value = f"(미지원 타입 : {key_type})"
                key_snapshot_list.append({"key" : key_name, "type" : key_type, "ttl_second" : ttl_second_count, "length" : total_length, "value" : value})
            return {"thread_id" : thread_id, "matched_key_count" : len(matched_key_list), "keys" : key_snapshot_list}
        except Exception as exception:
            raise HTTPException(status_code = 502, detail = f"REDIS SNAPSHOT FAILED : {exception}")

    async def get_thread_messages_async(self, thread_id : str) -> Dict[str, Any]:
        # 대화 내용 복원 : LangGraph 체크포인트(messages 채널)를 표시용 [{role, text, reasoning}] 으로 변환한다
        state_snapshot = await self._get_or_create_compiled_graph(None, None).aget_state({"configurable" : {"thread_id" : thread_id}})
        message_list   = state_snapshot.values.get("messages", []) if state_snapshot else []
        display_message_list = []
        for message in message_list:
            message_type = type(message).__name__
            body_text, reasoning_text = _extract_message_texts(message)
            if message_type == "HumanMessage" and body_text:
                display_message_list.append({"role" : "user", "text" : body_text})
            elif message_type in ("AIMessage", "AIMessageChunk") and body_text:   # 도구 호출 전용(본문 없는) AI 메시지는 표시에서 제외
                display_message_list.append({"role" : "agent", "text" : body_text, "reasoning" : reasoning_text or None})
        return {"thread_id" : thread_id, "messages" : display_message_list}

    async def diagnose_thread_async(self, thread_id : str) -> Dict[str, Any]:
        # ① 순수 체크포인트 로드 시간 : aget_state 전후를 perf_counter 로 측정한다
        runnable_configuration = {"configurable" : {"thread_id" : thread_id}}
        load_started_at        = time.perf_counter()
        state_snapshot         = await self._get_or_create_compiled_graph(None, None).aget_state(runnable_configuration)
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
        compiled_graph         = self._get_or_create_compiled_graph(stream_request.model, stream_request.reasoning_effort)

        def extract_chunk_texts(message_chunk):
            # 프로바이더별 청크 형식 통합 : ollama 는 additional_kwargs.reasoning_content,
            # google(Gemini) 은 content 리스트의 {"type":"thinking"} 블록으로 생각이 온다
            reasoning_text = (message_chunk.additional_kwargs or {}).get("reasoning_content", "")
            token_text     = ""
            if isinstance(message_chunk.content, str):
                token_text = message_chunk.content
            elif isinstance(message_chunk.content, list):
                for content_block in message_chunk.content:
                    if isinstance(content_block, str):
                        token_text += content_block
                    elif isinstance(content_block, dict):
                        if content_block.get("type") == "thinking":
                            reasoning_text += content_block.get("thinking", "")
                        elif content_block.get("type") == "text":
                            token_text += content_block.get("text", "")
            return reasoning_text, token_text

        async def generate_token_stream_async() -> AsyncIterator[str]:
            request_started_at   = time.perf_counter()
            is_first_token_seen  = False
            print(f"STREAM START : THREAD {stream_request.thread_id} - MODEL {stream_request.model or os.getenv('MODEL_NAME', 'qwen3-vl:4b')} - EFFORT {stream_request.reasoning_effort or 'default'}", flush = True)
            async for message_chunk, _metadata in compiled_graph.astream(input_dictionary, runnable_configuration, stream_mode = "messages"):
                # 생각 과정(reasoning) : 사용자가 대기 시간 동안 진행 상황을 볼 수 있게 실시간 전송한다 (NDJSON 모드 한정)
                reasoning_text, token_text = extract_chunk_texts(message_chunk)
                if reasoning_text and stream_request.include_reasoning:
                    yield json.dumps({"type" : "reasoning", "text" : reasoning_text}, ensure_ascii = False) + "\n"
                if not token_text:
                    continue
                if not is_first_token_seen:
                    is_first_token_seen = True
                    # TTFT(Time To First Token) : 첫 "답변" 토큰 기준 (생각 토큰 제외) — 프리필+생각 병목이 여기 숫자로 드러난다
                    print(f"TTFT : THREAD {stream_request.thread_id} - {(time.perf_counter() - request_started_at) * 1000:.0f}ms", flush = True)
                yield json.dumps({"type" : "token", "text" : token_text}, ensure_ascii = False) + "\n" if stream_request.include_reasoning else token_text
            print(f"TURN COMPLETED : THREAD {stream_request.thread_id} - TOTAL {(time.perf_counter() - request_started_at) * 1000:.0f}ms", flush = True)

        response_media_type = "application/x-ndjson" if stream_request.include_reasoning else "text/plain; charset=utf-8"
        return StreamingResponse(generate_token_stream_async(), media_type = response_media_type, headers = {"Cache-Control" : "no-cache", "X-Accel-Buffering" : "no"})

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
