##################################################
# 통합 FastAPI 애플리케이션 (LLM Job 서비스 + Think 병목 진단/채팅 모니터)
#
# 하나의 프로세스·포트에서 두 라우트 계열을 함께 호스팅한다.
#   - Job 서비스 (prefix /llm, /api/v1/orchestrator) : 비동기 job 제출·재구독·취소·타임라인,
#     JobReaper 유실 복구, 오케스트레이터 스트리밍
#   - 모니터 (루트 경로 /stream, /rooms, /models, /diagnose, /threads, /redis, /dev/api-client) :
#     동기 스트리밍 채팅, 채팅방 목록, 체크포인트 진단/복원/트리밍, 디버그 Redis 스냅샷
#
# 두 계열은 같은 PostgreSQL 체크포인트/Redis 인프라를 공유하되 서로 다른 그래프를 쓴다.
#   - 오케스트레이터 그래프 : Tavily 검색 + 리서치 서브에이전트 + 이미지 재주입 미들웨어
#   - 모니터 그래프         : ThinkTrimmingMiddleware (생각 토큰 트리밍/윈도잉), (모델, 강도)별 캐시
#
#   실행 : python backend/server.py   (기본 포트 8000)
##################################################

import io
import os
import re
import sys
import json
import time
import dataclasses
import uuid
import secrets
import asyncio
import uvicorn

# Windows : psycopg 비동기(체크포인터)는 ProactorEventLoop 를 지원하지 않으므로 Selector 정책으로 전환한다
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv                  import load_dotenv
from fastapi                 import FastAPI
from fastapi                 import File
from fastapi                 import HTTPException
from fastapi                 import Header
from fastapi                 import UploadFile
from fastapi.responses       import StreamingResponse
from fastapi.responses       import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib              import asynccontextmanager
from typing                  import Any
from typing                  import AsyncIterator
from typing                  import Dict
from typing                  import List
from typing                  import Optional
from redis.asyncio           import Redis
from pydantic                import BaseModel
from pydantic                import Field

from langchain_core.messages           import BaseMessage
from langchain_core.messages           import HumanMessage
from langchain_core.messages           import RemoveMessage
from langchain.agents.middleware.types import AgentMiddleware

# .env 는 프로젝트 모듈을 불러오기 전에 읽어야 한다.
# common/storage/s3_helper.py 의 s3_helper 싱글톤은 임포트되는 순간 os.getenv 로 접속 정보를 확정하는데,
# 그때 .env 가 아직 안 읽혀 있으면 버킷·키가 전부 None 인 클라이언트가 만들어져 업로드가 통째로 실패한다.
# (ServerApplication.__init__ 의 load_dotenv 는 이미 늦다)
load_dotenv()

from common.database.postgresql.postgresql_pool_manager        import PostgresqlPoolManager
from common.cache.redis_stream.redis_stream_client             import RedisStreamClient
from common.identifier.uuid_v7.uuid_v7_generator               import UUIDV7Generator
from common.config.environment_variable_helper                 import EnvironmentVariableHelper
from common.cache.redis_stream.redis_client_factory            import RedisClientFactory
from common.cache.redis_stream.redis_configuration_factory     import RedisConfigurationFactory
from common.security.password_helper                           import PasswordHelper
from common.security.auth_token_helper                         import AuthTokenHelper
from common.security.auth_secret_helper                        import AuthSecretHelper
from common.security.auth_token_renewal_middleware             import AuthTokenRenewalMiddleware
from common.config.model_preset_loader                         import ModelPresetLoader
from app.auth.user_schema_initializer                          import UserSchemaInitializer
from app.auth.user_repository                                  import UserRepository
from app.llm.job.job_configuration                             import JobConfiguration
from app.llm.repository.job_repository                         import JobRepository
from app.llm.repository.job_message_repository                 import JobMessageRepository
from app.llm.repository.job_event_repository                   import JobEventRepository
from app.llm.repository.job_chunk_repository                   import JobChunkRepository
from app.llm.repository.job_task_repository                    import JobTaskRepository
from app.llm.repository.chat_thread_repository                 import ChatThreadRepository
from app.llm.repository.thread_message_repository              import ThreadMessageRepository
from app.llm.repository.job_schema_initializer                 import JobSchemaInitializer
from app.llm.job.job_transfer.job_transfer                     import JobTransfer
from app.llm.job.job_executor.job_executor                     import JobExecutor
from app.llm.job.job_manager.job_manager                       import JobManager
from app.llm.job.job_subscription.job_subscription             import JobSubscription
from app.llm.job.job_manager.job_reaper                        import JobReaper
from app.llm.api.llm_api_router                                import LLMAPIRouter
from app.llm.api.chat_api_router                               import ChatAPIRouter
from app.llm.api.model_preset_response                         import ModelPreset
from app.llm.api.model_preset_response                         import ModelPresetsResponse
from app.llm.api.model_preset_response                         import ParameterSet
from app.llm.chat.chat_query_service                           import ChatQueryService
from app.llm.image.image_upload_service                        import ImageUploadService
from app.llm.image.vision_message_builder                      import VisionMessageBuilder
from common.database.postgresql.postgresql_configuration       import PostgresqlConfiguration
from common.cache.redis_stream.redis_configuration             import RedisConfiguration
from app.llm.agent.model_configuration                         import ModelConfiguration
from app.llm.agent.model_catalog                               import ModelCatalog
from app.llm.agent.deep_agent_factory                          import DeepAgentFactory
from app.llm.agent.chat_model_factory                          import ChatModelFactory
from app.llm.agent.tavily_search_tool_factory                  import TavilySearchToolFactory
from app.llm.agent.research_subagent_factory                   import ResearchSubAgentFactory
from app.llm.agent.binary_storage                              import LocalFileBinaryStorage
from app.llm.agent.image_attachment_interceptor                import ImageAttachmentInterceptor
from app.llm.agent.image_reinjection_middleware                import ImageReinjectionMiddleware
from app.llm.compression.compression_result                    import CompressionResult
from app.llm.compression.context_compression_configuration     import ContextCompressionConfiguration
from app.llm.compression.context_compression_middleware        import ContextCompressionMiddleware
from app.llm.compression.conversation_summarizer               import ConversationSummarizer
from app.llm.compression.conversation_summary_repository       import ConversationSummaryRepository
from app.orchestrator.api.orchestrator_api_router              import OrchestratorAPIRouter
from app.orchestrator.repository.checkpoint_schema_initializer import CheckpointSchemaInitializer
from app.orchestrator.service.chat_history_service             import ChatHistoryService
from app.orchestrator.service.chunk_flush_service              import ChunkFlushService
from app.orchestrator.service.graph_stream_executor            import GraphStreamExecutor
from app.orchestrator.service.redis_chunk_buffer               import RedisChunkBuffer

##################################################
# 생각 토큰(reasoning) 감지/트리밍 유틸리티
##################################################

# <think>...</think> 인라인 태그 (일부 서빙 조합은 생각 토큰을 content 안에 인라인으로 넣는다)
THINK_TAG_PATTERN = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def _to_text(raw_value : Any) -> str:
    # Redis 응답 정규화 : decode_responses 설정과 무관하게 항상 str 로 만든다 (bytes 면 디코드)
    return raw_value.decode("utf-8", errors = "replace") if isinstance(raw_value, bytes) else str(raw_value)


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


def _create_legacy_model_configuration(model_name : Optional[str] = None, reasoning_effort : Optional[str] = None) -> ModelConfiguration:
    # 모니터 그래프용 : 모델 카탈로그(config/models.yaml)가 없을 때의 .env(MODEL_*) 폴백 경로
    model_provider = os.getenv("MODEL_PROVIDER", "ollama").strip().lower()
    return ModelConfiguration(
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


##################################################
# [병목 해결 가이드] 생각 토큰 트리밍 + 윈도잉 미들웨어
#
# 원칙 : 체크포인트(원본 상태)는 건드리지 않고, "모델에게 보내는 프롬프트"만
# 슬림하게 만든다. before_model 훅은 반환값이 체크포인트에 다시 기록되므로 쓰지 않는다 —
# awrap_model_call 은 모델 요청(ModelRequest)만 override 하고 State 는 그대로 둔다.
##################################################
class ThinkTrimmingMiddleware(AgentMiddleware):
    # 모델 호출 직전에만 트리밍+윈도잉을 적용한다 (체크포인트 원본 보존)
    def __init__(self, window_message_count : int = 20) -> None:
        super().__init__()
        self.window_message_count = window_message_count

    async def awrap_model_call(self, request, handler):
        slim_message_list = prepare_model_input(request.messages, self.window_message_count)
        return await handler(request.override(messages = slim_message_list))


##################################################
# 모니터 요청 모델 (pydantic)
##################################################
class RegisterRequest(BaseModel):
    user_id  : str
    password : str


class LoginRequest(BaseModel):
    user_id  : str
    password : str


class RoomUpsertRequest(BaseModel):
    user_id          : str
    room_id          : str
    thread_id        : str
    title            : str            = "새 대화"
    model            : Optional[str]  = None
    reasoning_effort : Optional[str]  = None


class CompressedInfoResponse(BaseModel):
    # 대화 압축 결과. /stream 은 NDJSON 스트림이라 본문 JSON 이 없으므로
    # {"type" : "compressed_info", ...} 이벤트로 첫 부분에 실려 나간다.
    is_compressed : bool
    saved_tokens  : int           = 0
    summary       : Optional[str] = None


class BookmarkUpsertRequest(BaseModel):
    # 북마크 대상은 "방 안에서 몇 번째 답변인가"(agent_index) 로 식별한다.
    # thread_id 는 대화 전체를 가리키는 값이라 답변 하나를 지목할 수 없어 쓰지 않는다.
    bookmark_id  : str
    room_id      : str
    agent_index  : int
    text         : str            = ""     # 목록 미리보기용 스냅샷 (체크포인트를 열지 않고 사이드바를 그리기 위함)
    completed_at : Optional[int]  = None   # 답변 완료 시각 (epoch ms)
    memo         : Optional[str]  = None   # 사용자 메모. None 이면 "건드리지 않음" — 기존 메모를 지우지 않는다


class BookmarkMemoUpdateRequest(BaseModel):
    # 메모만 부분 수정한다 (PATCH). 빈 문자열이면 메모 삭제로 취급해 NULL 로 저장한다.
    memo : Optional[str] = None


class StreamRequest(BaseModel):
    thread_id         : str
    message           : str
    model             : Optional[str] = None    # 요청별 모델 선택 (미지정 시 .env 기본 모델)
    reasoning_effort  : Optional[str] = None    # 생각 강도 : low | medium | high | None(모델 기본)
    include_reasoning : bool          = False   # True : NDJSON 이벤트 스트림({"type":"reasoning"|"token","text":...}) 으로 생각 과정을 함께 전송
                                                # False : 답변 토큰만 평문 스트림 (기존 클라이언트 하위호환)
    referenced_text   : Optional[str] = None    # 이전 답변에서 드래그해 "참조하기"로 담은 발췌.
                                                # 있으면 [참조 내용]/[질문] 두 블록으로 조합해 모델에 전달한다.
    preset_name       : Optional[str] = None    # LLM 파라미터 프리셋: LOW / MEDIUM / HIGH
                                                # 지정 시 온도, top_p, max_tokens 등 하이퍼파라미터를 적용한다.
    referenced_message_id_list : List[str] = Field(default_factory = list)
                                                # 우클릭으로 통째로 고른 이전 답변들의 ID ("agent-0", "agent-3" …).
                                                # 체크포인트에서 본문을 찾아 <referenced_context> 블록으로 묶어 전달한다.
    image_url_list : List[str] = Field(default_factory = list)
                                                # POST /api/upload 로 MinIO 에 올린 이미지들의 접근 URL.
                                                # 있으면 질문을 OpenAI 멀티모달 규격(text + image_url 블록)으로 조립해 Vision 모델에 넘긴다.


class TruncateThreadRequest(BaseModel):
    # 유지할 사용자 메시지 개수. 그 다음 사용자 메시지부터 이후 전부를 체크포인트에서 제거한다.
    # (특정 질문을 수정해 그 지점부터 대화를 다시 이어갈 때 사용)
    #
    # 개수 기준인 이유 : 실패/중단된 턴은 프론트 목록에는 남지만 체크포인트에는 기록되지 않아
    # 양쪽 순번이 어긋난다. 개수 기준이면 어긋나도 "제거할 것 없음"으로 안전하게 끝난다.
    keep_human_message_count : int


class ServerApplication:
    BOOKMARK_MEMO_MAXIMUM_LENGTH   = 1000   # 북마크 메모 최대 길이 (기본값 : 1000)
    REFERENCED_TEXT_MAXIMUM_LENGTH = 2000   # 참조 발췌 최대 길이 (기본값 : 2000) — 프롬프트가 발췌로 뒤덮이는 것을 막는다
    REFERENCED_MESSAGE_MAXIMUM_COUNT  = 10    # 통째로 참조할 수 있는 이전 답변 개수 (기본값 : 10)
    REFERENCED_MESSAGE_MAXIMUM_LENGTH = 4000  # 참조 답변 1건당 최대 길이 (기본값 : 4000)
    REFERENCED_MESSAGE_ID_PREFIX      = "agent-"   # 답변 ID 형식 : agent-{답변 순번(0부터)}
    DUPLICATE_USER_MESSAGE            = "이미 등록된 유저입니다."   # 회원가입 중복 ID 안내 (409 응답 본문에 그대로 실린다)

    def __init__(self) -> None:
        load_dotenv()
        self.postgresql_pool_manager = PostgresqlPoolManager(ServerApplication._get_postgresql_configuration())
        self.redis_stream_client     = RedisStreamClient(ServerApplication._get_redis_configuration())
        self.uuid_v7_generator       = UUIDV7Generator()
        self.job_configuration       = JobConfiguration()
        self.job_repository          = JobRepository(self.postgresql_pool_manager)
        self.job_message_repository  = JobMessageRepository(self.postgresql_pool_manager)
        self.job_event_repository    = JobEventRepository(self.postgresql_pool_manager)
        self.job_chunk_repository    = JobChunkRepository(self.postgresql_pool_manager)
        self.job_task_repository     = JobTaskRepository(self.postgresql_pool_manager)
        self.chat_thread_repository  = ChatThreadRepository(self.postgresql_pool_manager)
        self.thread_message_repository = ThreadMessageRepository(self.postgresql_pool_manager)
        self.job_schema_initializer  = JobSchemaInitializer(self.postgresql_pool_manager)
        self.user_schema_initializer = UserSchemaInitializer(self.postgresql_pool_manager)
        self.user_repository         = UserRepository(self.postgresql_pool_manager)
        # 대화 압축 : 설정은 기동 시 확정하고, 저장소/생성기는 체크포인트 풀이 열린 뒤 주입한다
        self.compression_configuration       = ServerApplication._get_context_compression_configuration()
        self.conversation_summary_repository = None
        self.conversation_summarizer         = None
        # 인증 토큰 : 비밀키는 재시작해도 같은 값이어야 한다.
        # 예전에는 환경변수가 없으면 매 기동마다 secrets.token_hex() 로 새로 만들었는데,
        # 그 탓에 서버를 재시작할 때마다 발급해 둔 토큰이 전부 서명 검증에 실패해 사용자가 로그아웃됐다.
        # 이제 환경변수 > 로컬 파일 > (없으면) 새로 만들어 파일에 저장 순으로 고정 값을 확보한다.
        self.auth_token_secret           = AuthSecretHelper.resolve_secret(
            os.getenv("AUTH_TOKEN_SECRET"), os.getenv("AUTH_TOKEN_SECRET_FILE_PATH", ".auth_token_secret"))
        self.auth_token_ttl_second_count = int(os.getenv("AUTH_TOKEN_TTL_SECOND_COUNT", "604800"))   # 기본 7일
        self.job_transfer            = JobTransfer(
            self.postgresql_pool_manager,
            self.redis_stream_client,
            self.uuid_v7_generator,
            self.job_configuration,
            self.job_repository,
            self.job_message_repository,
            self.job_event_repository,
            self.job_chunk_repository,
            self.job_task_repository,
            self.chat_thread_repository,
            self.thread_message_repository
        )
        self.job_executor = JobExecutor(
            self.redis_stream_client,
            self.uuid_v7_generator,
            self.job_configuration,
            self.job_repository,
            self.job_message_repository,
            self.job_event_repository,
            self.job_chunk_repository,
            self.job_task_repository,
            self.job_transfer
        )
        self.job_manager = JobManager(
            self.redis_stream_client,
            self.uuid_v7_generator,
            self.job_configuration,
            ServerApplication._get_model_configuration(),
            self.job_repository,
            self.job_message_repository,
            self.job_event_repository,
            self.job_chunk_repository,
            self.job_task_repository,
            self.chat_thread_repository,
            self.thread_message_repository,
            self.job_executor,
            self.job_transfer
        )
        self.job_subscription = JobSubscription(
            self.redis_stream_client,
            self.job_configuration,
            self.job_repository,
            self.job_message_repository,
            self.job_event_repository,
            self.job_chunk_repository
        )
        self.job_reaper         = JobReaper(self.redis_stream_client, self.job_configuration, self.job_transfer, self.job_repository)
        self.llm_api_router     = LLMAPIRouter(self.job_manager, self.job_subscription)
        self.chat_query_service = ChatQueryService(
            self.chat_thread_repository,
            self.thread_message_repository,
            self.job_repository,
            self.job_chunk_repository,
            self.job_task_repository
        )
        self.chat_api_router = ChatAPIRouter(self.chat_query_service)

        # 오케스트레이터 도메인 (Redis 버퍼링 → llm_* 스키마 벌크 저장, 저장은 llm 리포지토리 재사용)
        # redis.asyncio 클라이언트는 첫 명령 시점에 지연 연결되므로 여기서 생성해도 안전하다 (연결 확인은 lifespan ping)
        # 모니터의 디버그 Redis 스냅샷 / 런 청크 버퍼도 이 단일 클라이언트를 공유한다
        self.orchestrator_redis_client    = ServerApplication._create_orchestrator_redis_client()
        self.redis_chunk_buffer           = RedisChunkBuffer(self.orchestrator_redis_client)
        self.chat_history_service         = ChatHistoryService(self.job_repository, self.job_message_repository)
        self.chunk_flush_service          = ChunkFlushService(self.postgresql_pool_manager, self.redis_chunk_buffer, self.job_repository, self.job_message_repository, self.chat_thread_repository)
        self.graph_stream_executor        = GraphStreamExecutor(self.redis_chunk_buffer)

        # 체크포인트 설정 : lifespan 에서 PostgresSaver 를 만들어 두 그래프가 공유한다
        # (AsyncPostgresSaver 는 async 컨텍스트가 필요하므로 생성자에서는 비체크포인트 오케스트레이터 그래프로 시작)
        self.is_checkpoint_enabled        = EnvironmentVariableHelper.get_boolean("CHECKPOINT_ENABLED", False)
        self.checkpoint_partition_count   = int(os.getenv("CHECKPOINT_PARTITION_COUNT", "8"))
        self.checkpoint_schema_initializer = CheckpointSchemaInitializer(self.postgresql_pool_manager, self.checkpoint_partition_count)
        self.checkpoint_connection_pool   = None  # psycopg AsyncConnectionPool (lifespan 에서 생성/종료)
        self.checkpoint_saver             = None  # AsyncPostgresSaver (lifespan 에서 생성, 모니터 그래프가 사용)

        # 모니터 그래프 캐시 : (모델 키, 생각 강도) → 컴파일 그래프. 체크포인터를 공유하므로 스레드 이력은 설정과 무관하게 이어진다
        self.model_catalog                = ModelCatalog.load_default()   # config/models.yaml (없으면 None → .env 폴백)
        self.compiled_graph_dictionary    = {}
        self.is_run_buffer_disabled       = False   # Redis 미가동 등으로 버퍼링 실패 시 True (스트리밍은 계속)

        # 이미지 격리 파이프라인 : 라우터에서 격리(detach) → 체크포인트에는 참조만 → 모델 직전 재주입(reinject)
        # 이미지 입력이 없는 현재는 전 구간 무비용 패스스루로 동작한다
        # 이미지 업로드(MinIO) + Vision 메시지 조립
        self.image_upload_service         = ImageUploadService.create_from_environment()
        self.vision_message_builder       = VisionMessageBuilder.create_from_environment()
        # 어느 스토리지를 바라보는지 기동 시 찍어 둔다 — 환경변수가 .env 를 이겨 엉뚱한 곳에 붙어도 로그로 바로 드러난다
        print(self.image_upload_service.describe_storage_configuration(), flush = True)
        print(f"VISION IMAGE MODE : inline_base64={self.vision_message_builder.is_inline_base64}", flush = True)
        self.binary_storage               = LocalFileBinaryStorage(os.getenv("ATTACHMENT_STORAGE_DIRECTORY", "./attachment_storage"))
        self.image_attachment_interceptor = ImageAttachmentInterceptor(self.binary_storage, detach_minimum_byte_count = int(os.getenv("ATTACHMENT_DETACH_MINIMUM_BYTE_COUNT", "4096")))

        self.orchestrator_compiled_graph  = self._create_orchestrator_compiled_graph()
        self.orchestrator_api_router      = OrchestratorAPIRouter(self.orchestrator_compiled_graph, self.uuid_v7_generator, self.chat_history_service, self.chunk_flush_service, self.graph_stream_executor, self.redis_chunk_buffer, self.is_checkpoint_enabled, self.image_attachment_interceptor)

        self.application = FastAPI(title = "LLM Orchestrator (Job Service + Monitor)", lifespan = self.lifespan_async)
        # 개발용 API 테스트 페이지(/dev/api-client)·로컬 진단 대시보드에서의 교차 출처 호출 허용
        # 토큰 자동 연장 : 인증된 요청이 지나갈 때 남은 수명이 절반 아래면 새 토큰을 헤더로 함께 내려준다.
        # (CORS 보다 먼저 등록해야 CORS 가 바깥쪽에 놓여 여기서 붙인 헤더까지 노출 처리된다)
        self.application.add_middleware(AuthTokenRenewalMiddleware,
                                        secret           = self.auth_token_secret,
                                        ttl_second_count = self.auth_token_ttl_second_count)
        # allow_credentials 는 켜지 않는다 : 이 서비스는 쿠키가 아니라 Authorization: Bearer 헤더로 인증한다.
        # (allow_origins=["*"] 와 allow_credentials=True 는 브라우저가 거부하는 조합이기도 하다)
        # 프론트가 갱신 토큰 헤더를 읽으려면 expose_headers 에 반드시 들어가 있어야 한다.
        self.application.add_middleware(CORSMiddleware,
                                        allow_origins  = os.getenv("CORS_ALLOW_ORIGIN_LIST", "*").split(","),
                                        allow_methods  = ["*"],
                                        allow_headers  = ["*"],
                                        expose_headers = ["X-Run-Id", "X-Thread-Id", AuthTokenRenewalMiddleware.REFRESHED_TOKEN_HEADER_NAME])
        # Job 서비스 라우터 (prefix : /llm, /api/v1/orchestrator)
        self.application.include_router(self.llm_api_router.get_router())
        self.application.include_router(self.chat_api_router.get_router())
        self.application.include_router(self.orchestrator_api_router.get_router())
        # 인증 라우트 (사용자 등록 / 로그인 — user_id + 비밀번호)
        self.application.add_api_route("/auth/register",               self.register_user_async,       methods = ["POST"])
        self.application.add_api_route("/auth/login",                  self.login_user_async,          methods = ["POST"])
        # 모니터 라우트 (루트 경로 — Job 라우터와 경로가 겹치지 않는다)
        self.application.add_api_route("/diagnose",                     self.diagnose_thread_async,     methods = ["GET"])
        self.application.add_api_route("/models",                       self.list_models_async,         methods = ["GET"])
        self.application.add_api_route("/config/presets",              self.list_model_presets_async,  methods = ["GET"])
        self.application.add_api_route("/api/upload",                  self.upload_image_async,        methods = ["POST"])   # 이미지 → MinIO
        self.application.add_api_route("/stream",                       self.stream_async,              methods = ["POST"])
        self.application.add_api_route("/rooms",                        self.list_rooms_async,          methods = ["GET"])
        self.application.add_api_route("/rooms",                        self.upsert_room_async,         methods = ["POST"])
        self.application.add_api_route("/rooms/{room_id}",              self.delete_room_async,         methods = ["DELETE"])
        self.application.add_api_route("/bookmarks",                    self.list_bookmarks_async,      methods = ["GET"])
        self.application.add_api_route("/bookmarks",                    self.upsert_bookmark_async,     methods = ["POST"])
        self.application.add_api_route("/bookmarks/{bookmark_id}",      self.update_bookmark_memo_async, methods = ["PATCH"])   # 메모만 부분 수정
        self.application.add_api_route("/bookmarks/{bookmark_id}",      self.delete_bookmark_async,     methods = ["DELETE"])
        self.application.add_api_route("/threads/{thread_id}/messages", self.get_thread_messages_async, methods = ["GET"])
        self.application.add_api_route("/threads/{thread_id}/truncate", self.truncate_thread_async,     methods = ["POST"])   # 질문 수정 후 그 지점부터 재개
        self.application.add_api_route("/redis/{thread_id}",            self.get_redis_snapshot_async,  methods = ["GET"])   # 디버그 패널용 Redis 캐시 조회
        self.application.add_api_route("/dev/api-client",               self.get_api_client_page_async, methods = ["GET"], include_in_schema = False)   # APIDog 스타일 API 테스트 페이지

    @staticmethod
    def _get_context_compression_configuration() -> ContextCompressionConfiguration:
        # 대화 압축 임계치 : .env 로 조정 가능. CONTEXT_COMPRESSION_ENABLED=false 로 완전히 끌 수 있다.
        return ContextCompressionConfiguration(
            recent_message_keep_count   = int(os.getenv("CONTEXT_COMPRESSION_RECENT_KEEP_COUNT",   "10")),
            trigger_message_count       = int(os.getenv("CONTEXT_COMPRESSION_TRIGGER_MESSAGE_COUNT", "14")),
            trigger_token_count         = int(os.getenv("CONTEXT_COMPRESSION_TRIGGER_TOKEN_COUNT", "3000")),
            summary_line_count          = int(os.getenv("CONTEXT_COMPRESSION_SUMMARY_LINE_COUNT",  "4")),
            summary_maximum_token_count = int(os.getenv("CONTEXT_COMPRESSION_SUMMARY_MAXIMUM_TOKEN_COUNT", "512")),
            is_enabled                  = os.getenv("CONTEXT_COMPRESSION_ENABLED", "true").strip().lower() != "false"
        )

    @staticmethod
    def _get_postgresql_configuration() -> PostgresqlConfiguration:
        return PostgresqlConfiguration(
            host                     =     os.getenv("POSTGRESQL_HOST"                    , "localhost"),
            port                     = int(os.getenv("POSTGRESQL_PORT"                    , "5432"     )),
            database_name            =     os.getenv("POSTGRESQL_DATABASE"                , os.getenv("POSTGRESQL_DATABASE_NAME", "postgres")),
            user_name                =     os.getenv("POSTGRESQL_USER"                    , os.getenv("POSTGRESQL_USER_NAME"    , "postgres")),
            password                 =     os.getenv("POSTGRESQL_PASSWORD"                , "postgres"),
            minimum_connection_count = int(os.getenv("POSTGRESQL_MINIMUM_CONNECTION_COUNT", "1"       )),
            maximum_connection_count = int(os.getenv("POSTGRESQL_MAXIMUM_CONNECTION_COUNT", "10"      ))
        )

    @staticmethod
    def _get_redis_configuration() -> RedisConfiguration:
        return RedisConfigurationFactory.create_from_environment()

    @staticmethod
    def _get_model_configuration() -> ModelConfiguration:
        # 오케스트레이터/Job 그래프용 : 모델 카탈로그(config/models.yaml) 우선. 카탈로그가 없으면 .env(MODEL_*) 폴백
        model_catalog = ModelCatalog.load_default()
        if model_catalog is not None:
            return model_catalog.create_model_configuration(model_catalog.get_default_model_key())
        default_header_dictionary = EnvironmentVariableHelper.get_optional_dictionary("MODEL_DEFAULT_HEADERS")
        if default_header_dictionary is not None and not all(isinstance(field_name, str) and isinstance(field_value, str) for field_name, field_value in default_header_dictionary.items()):
            raise ValueError("INVALID MODEL DEFAULT HEADERS : MODEL_DEFAULT_HEADERS")
        return ModelConfiguration(
            provider                  = os.getenv("MODEL_PROVIDER", "openai"),
            model_name                = os.getenv("MODEL_NAME", "gpt-4o-mini"),
            api_key                   = os.getenv("MODEL_API_KEY"),
            base_url                  = os.getenv("MODEL_BASE_URL"),
            temperature               = float(os.getenv("MODEL_TEMPERATURE", "0.0")),
            maximum_token_count       = EnvironmentVariableHelper.get_optional_integer("MODEL_MAXIMUM_TOKEN_COUNT"),
            timeout_second_count      = float(os.getenv("MODEL_TIMEOUT_SECOND_COUNT", "120.0")),
            maximum_retry_count       = int(os.getenv("MODEL_MAXIMUM_RETRY_COUNT", "2")),
            default_header_dictionary = default_header_dictionary,
            extra_body_dictionary     = EnvironmentVariableHelper.get_optional_dictionary("MODEL_EXTRA_BODY"),
            reasoning_enabled         = EnvironmentVariableHelper.get_boolean("MODEL_REASONING_ENABLED", False),
            context_token_count       = EnvironmentVariableHelper.get_optional_integer("MODEL_CONTEXT_TOKEN_COUNT"),
            reasoning_effort          = os.getenv("MODEL_REASONING_EFFORT", "").strip() or None
        )

    def _create_orchestrator_compiled_graph(self, checkpointer = None):
        # 오케스트레이터 그래프 조립 : Tavily 검색 도구가 있으면 웹 리서치 서브에이전트를 붙여
        # 메인 → task() → 서브에이전트 트리 구조로 컴파일된다 (TAVILY_API_KEY 미설정 시 단일 노드)
        search_tool   = TavilySearchToolFactory.create()
        subagent_list = ResearchSubAgentFactory.create_subagent_list(search_tool)
        tool_list     = [search_tool] if search_tool is not None else None
        return DeepAgentFactory.create(
            ServerApplication._get_model_configuration(),
            tool_list       = tool_list,
            checkpointer    = checkpointer,
            subagent_list   = subagent_list,
            middleware_list = [ImageReinjectionMiddleware(self.image_attachment_interceptor)]
        )

    @staticmethod
    def _create_orchestrator_redis_client() -> Redis:
        # 오케스트레이터 청크 버퍼용 redis.asyncio 클라이언트 (기존 REDIS_* 환경변수 재사용)
        return RedisClientFactory.create_client(ServerApplication._get_redis_configuration(), decode_responses = True)

    ##################################################
    # 모니터 그래프 (ThinkTrimmingMiddleware, 모델별 캐시)
    ##################################################

    def _get_default_model_key(self) -> str:
        # 카탈로그가 있으면 카탈로그 기본 키, 없으면 .env 기본 모델명
        return self.model_catalog.get_default_model_key() if self.model_catalog is not None else os.getenv("MODEL_NAME", "qwen3-vl:4b")

    def _resolve_model_configuration(self, model_name : Optional[str], reasoning_effort : Optional[str] = None) -> ModelConfiguration:
        # 카탈로그 우선 : model_name 은 카탈로그 키(config/models.yaml)다. 카탈로그가 없거나 키가 없으면 .env 폴백
        if self.model_catalog is not None:
            model_key = model_name or self.model_catalog.get_default_model_key()
            if self.model_catalog.has_model(model_key):
                return self.model_catalog.create_model_configuration(model_key, reasoning_effort)
        return _create_legacy_model_configuration(model_name, reasoning_effort)

    @staticmethod
    def _create_monitor_compiled_graph(checkpoint_saver, model_configuration : ModelConfiguration, context_compression_middleware = None):
        # 진단/채팅용 그래프 : 운영과 동일한 deepagents 그래프에 생각 토큰 트리밍 미들웨어를 얹는다.
        # 압축 미들웨어는 트리밍 뒤에 온다 — 생각 토큰이 걷힌 뒤의 메시지를 대상으로 창을 잡아야
        # 요약과 최근 원본이 같은 기준으로 정렬된다.
        middleware_list = [ThinkTrimmingMiddleware()]
        if context_compression_middleware is not None:
            middleware_list.append(context_compression_middleware)
        return DeepAgentFactory.create(
            model_configuration,
            checkpointer    = checkpoint_saver,
            middleware_list = middleware_list
        )

    def _get_or_create_compiled_graph(self, model_name : Optional[str], reasoning_effort : Optional[str] = None):
        # (모델, 생각 강도)별 그래프를 지연 생성해 캐싱한다 (같은 체크포인터를 공유하므로 스레드 이력은 설정과 무관하게 이어진다)
        cache_key = (model_name or self._get_default_model_key(), reasoning_effort)
        if cache_key not in self.compiled_graph_dictionary:
            context_compression_middleware = None
            if self.conversation_summary_repository is not None:
                context_compression_middleware = ContextCompressionMiddleware(self.conversation_summary_repository, self.compression_configuration)
            self.compiled_graph_dictionary[cache_key] = ServerApplication._create_monitor_compiled_graph(
                self.checkpoint_saver, self._resolve_model_configuration(cache_key[0], cache_key[1]), context_compression_middleware)
        return self.compiled_graph_dictionary[cache_key]

    async def _initialize_checkpointer_async(self) -> None:
        # PostgreSQL 체크포인터 초기화 : 파티션 스키마 선생성 → psycopg 풀 → setup() → 두 그래프가 공유
        # (선주입된 마이그레이션 버전 덕분에 setup() 은 신규 마이그레이션이 없는 한 no-op 이다)
        # 모니터 그래프는 체크포인터가 필수이므로 CHECKPOINT_ENABLED 와 무관하게 항상 초기화한다.
        from psycopg.rows                       import dict_row
        from psycopg_pool                       import AsyncConnectionPool
        from langgraph.checkpoint.postgres.aio  import AsyncPostgresSaver

        postgresql_configuration = ServerApplication._get_postgresql_configuration()
        connection_info_text     = f"host={postgresql_configuration.host} port={postgresql_configuration.port} dbname={postgresql_configuration.database_name} user={postgresql_configuration.user_name} password={postgresql_configuration.password}"

        await self.checkpoint_schema_initializer.initialize_schema_async()
        self.checkpoint_connection_pool = AsyncConnectionPool(connection_info_text, min_size = 1, max_size = 5, open = False, kwargs = {"autocommit" : True, "row_factory" : dict_row})
        await self.checkpoint_connection_pool.open()
        checkpoint_saver = AsyncPostgresSaver(self.checkpoint_connection_pool)
        await checkpoint_saver.setup()
        self.checkpoint_saver = checkpoint_saver

        # 대화 압축 : 요약 저장소와 생성기는 체크포인트 풀(chat_room 이 사는 DB)을 공유한다
        self.conversation_summary_repository = ConversationSummaryRepository(self.checkpoint_connection_pool)
        self.conversation_summarizer         = ConversationSummarizer(self.conversation_summary_repository, self.compression_configuration)

        # 오케스트레이터 그래프 : 기존 동작 보존 — CHECKPOINT_ENABLED 일 때만 체크포인터가 주입된 그래프로 교체
        if self.is_checkpoint_enabled:
            self.orchestrator_compiled_graph            = self._create_orchestrator_compiled_graph(checkpointer = checkpoint_saver)
            self.orchestrator_api_router.compiled_graph = self.orchestrator_compiled_graph

        # 모니터 기본 모델 그래프 선생성 (체크포인터 공유)
        self._get_or_create_compiled_graph(None)

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

-- 대화 압축 상태 : 방을 나갔다 들어와도 요약이 유지되도록 chat_room 에 함께 둔다.
-- (기존 배포에도 붙어야 하므로 CREATE 가 아니라 ADD COLUMN IF NOT EXISTS 로 추가한다)
-- summarized_message_count : 어디까지 요약에 반영했는지 — 없으면 압축할 때마다 옛 대화를 다시 요약한다.
ALTER TABLE chat_room ADD COLUMN IF NOT EXISTS summary                  TEXT;
ALTER TABLE chat_room ADD COLUMN IF NOT EXISTS summarized_message_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE chat_room ADD COLUMN IF NOT EXISTS summary_updated_at       TIMESTAMPTZ;

-- 북마크 : "방 안에서 N 번째 답변"단위로 저장한다.
-- chat_room 에 불리언 칼럼을 두지 않는 이유 : thread_id 는 대화 전체를 가리키므로 답변 하나를 지목할 수 없다.
-- text 는 미리보기 스냅샷 — 이게 없으면 사이드바 목록을 그릴 때마다 방마다 체크포인트를 통째로 열어야 한다.
CREATE TABLE IF NOT EXISTS chat_bookmark
(
    bookmark_id  TEXT        PRIMARY KEY,
    user_id      TEXT        NOT NULL,
    room_id      TEXT        NOT NULL REFERENCES chat_room (room_id) ON DELETE CASCADE,
    agent_index  INTEGER     NOT NULL,
    text         TEXT        NOT NULL DEFAULT '',
    completed_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (room_id, agent_index)
);
CREATE INDEX IF NOT EXISTS idx_chat_bookmark_user_created ON chat_bookmark (user_id, created_at DESC);

-- 메모 : 북마크한 답변에 사용자가 직접 남기는 짧은 기록.
-- (기존 배포에도 붙어야 하므로 CREATE 가 아니라 ADD COLUMN IF NOT EXISTS 로 추가한다)
-- NULL 은 "메모 없음" — 빈 문자열과 구분해 두어야 upsert 시 COALESCE 로 기존 메모를 보존할 수 있다.
ALTER TABLE chat_bookmark ADD COLUMN IF NOT EXISTS memo TEXT;
""")

    ##################################################
    # 인증 라우트 핸들러 (사용자 등록 / 로그인)
    ##################################################

    def _issue_token(self, user_id : str) -> str:
        return AuthTokenHelper.create_token(user_id, self.auth_token_secret, self.auth_token_ttl_second_count)

    def _require_authenticated_user_id(self, authorization : Optional[str]) -> str:
        # Authorization: Bearer <token> 를 검증하고 인증된 user_id 를 반환한다 (없거나 무효면 401)
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code = 401, detail = "AUTHENTICATION REQUIRED")
        token   = authorization[len("Bearer "):].strip()
        user_id = AuthTokenHelper.verify_token(token, self.auth_token_secret)
        if user_id is None:
            raise HTTPException(status_code = 401, detail = "INVALID OR EXPIRED TOKEN")
        return user_id

    async def _assert_thread_accessible_async(self, user_id : str, thread_id : str) -> None:
        # 스레드 소유권 검증 : 다른 사용자가 소유(chat_room)한 thread_id 면 403.
        # 미등록(신규) 스레드나 본인 소유 스레드는 허용한다.
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute("SELECT 1 FROM chat_room WHERE thread_id = %s AND user_id <> %s LIMIT 1", (thread_id, user_id))
            if await cursor.fetchone() is not None:
                raise HTTPException(status_code = 403, detail = "THREAD ACCESS DENIED")

    async def register_user_async(self, register_request : RegisterRequest) -> Dict[str, Any]:
        # 신규 사용자 등록 : user_id 중복이면 409, 유효성 실패면 400. 성공 시 인증 토큰 발급
        user_id  = register_request.user_id.strip()
        password = register_request.password
        if not user_id or not password:
            raise HTTPException(status_code = 400, detail = "USER ID AND PASSWORD ARE REQUIRED")
        if len(password) < 4:
            raise HTTPException(status_code = 400, detail = "PASSWORD TOO SHORT : MINIMUM 4 CHARACTERS")
        password_hash = PasswordHelper.hash_password(password)
        is_created    = await self.user_repository.create_user_async(user_id, password_hash)
        if not is_created:
            # 화면에 그대로 띄우는 문구라 한국어로 내려준다 (다른 오류 메시지는 개발자용이라 영어를 유지).
            # 응답에 user_id 를 되싣지 않는다 — 아무나 가입 API 를 두드려 계정 존재 여부를 확인할 수 있게 되기 때문.
            raise HTTPException(status_code = 409, detail = ServerApplication.DUPLICATE_USER_MESSAGE)
        return {"user_id" : user_id, "token" : self._issue_token(user_id), "status" : "registered"}

    async def login_user_async(self, login_request : LoginRequest) -> Dict[str, Any]:
        # 로그인 검증 : user_id 없음/비밀번호 불일치는 동일하게 401 (계정 존재 여부 노출 방지). 성공 시 인증 토큰 발급
        user_id     = login_request.user_id.strip()
        stored_hash = await self.user_repository.get_password_hash_async(user_id)
        if stored_hash is None or not PasswordHelper.verify_password(login_request.password, stored_hash):
            raise HTTPException(status_code = 401, detail = "INVALID USER ID OR PASSWORD")
        return {"user_id" : user_id, "token" : self._issue_token(user_id), "status" : "ok"}

    ##################################################
    # 모니터 라우트 핸들러
    ##################################################

    async def list_models_async(self) -> Dict[str, Any]:
        # 프론트 모델 선택 드롭다운용.
        # 카탈로그 모드 : config/models.yaml 의 모델 키 목록을 그대로 노출한다 (요청의 model 값 = 카탈로그 키)
        if self.model_catalog is not None:
            return {"default_model" : self.model_catalog.get_default_model_key(), "models" : self.model_catalog.get_model_key_list(), "provider" : "catalog"}
        # 폴백 모드 : ollama 는 설치 모델을 프록시, 그 외 프로바이더는 기본 모델만 노출한다
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

    async def list_model_presets_async(self) -> ModelPresetsResponse:
        # LLM 모델 파라미터 프리셋 목록 반환 (LOW / MEDIUM / HIGH)
        presets_dictionary = ModelPresetLoader.load_presets()
        presets_object_dictionary = {}
        for preset_name, preset_params in presets_dictionary.items():
            # 부분 파라미터 세트 (thinking, answer) 변환
            thinking_params = preset_params.get("thinking")
            answer_params   = preset_params.get("answer")
            thinking_object = ParameterSet(**thinking_params) if thinking_params else None
            answer_object   = ParameterSet(**answer_params) if answer_params else None
            # 메인 프리셋 객체 생성
            preset_object = ModelPreset(
                name                 = preset_name,
                temperature          = preset_params.get("temperature", 0.5),
                top_p                = preset_params.get("top_p", 0.9),
                max_completion_tokens = preset_params.get("max_completion_tokens", 512),
                timeout              = preset_params.get("timeout", 120),
                max_retries          = preset_params.get("max_retries", 3),
                stream_usage         = preset_params.get("stream_usage", True),
                default_headers      = preset_params.get("default_headers", {}),
                extra_body           = preset_params.get("extra_body", {}),
                num_return_sequences = preset_params.get("num_return_sequences", 1),
                thinking             = thinking_object,
                answer               = answer_object
            )
            presets_object_dictionary[preset_name] = preset_object
        return ModelPresetsResponse(presets = presets_object_dictionary, available_preset_names = list(presets_object_dictionary.keys()))

    async def upload_image_async(self, file : UploadFile = File(...), authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        # 이미지를 MinIO 에 올리고 Vision 모델이 읽을 수 있는 URL 을 돌려준다.
        # 인증을 요구하는 이유 : 열어두면 누구나 사내 스토리지에 파일을 쌓을 수 있다.
        self._require_authenticated_user_id(authorization)

        if not self.image_upload_service.is_allowed_content_type(file.content_type):
            raise HTTPException(status_code = 400, detail = "이미지 파일만 업로드할 수 있습니다. (png / jpeg / webp / gif)")

        # 크기 검사는 파일을 통째로 읽어서 한다. UploadFile 은 스풀링되어 큰 파일은 디스크로 넘어가므로
        # 메모리를 잡아먹지 않고, 헤더의 Content-Length 는 위조될 수 있어 믿지 않는다.
        file_bytes = await file.read()
        if len(file_bytes) == 0:
            raise HTTPException(status_code = 400, detail = "빈 파일입니다.")
        if len(file_bytes) > self.image_upload_service.maximum_byte_count:
            maximum_megabyte = self.image_upload_service.maximum_byte_count / (1024 * 1024)
            raise HTTPException(status_code = 413, detail = f"이미지가 너무 큽니다. (최대 {maximum_megabyte:.0f}MB)")

        object_key    = self.image_upload_service.build_object_key(file.content_type)
        is_uploaded   = await asyncio.to_thread(
            self.image_upload_service.upload_image, io.BytesIO(file_bytes), object_key, file.content_type)
        if not is_uploaded:
            raise HTTPException(status_code = 502, detail = "이미지 저장소에 업로드하지 못했습니다. 스토리지 상태를 확인해주세요.")

        image_url = await asyncio.to_thread(self.image_upload_service.build_image_url, object_key)
        if not image_url:
            raise HTTPException(status_code = 502, detail = "이미지 접근 URL 을 만들지 못했습니다.")
        return {"object_key" : object_key, "image_url" : image_url, "content_type" : file.content_type, "byte_count" : len(file_bytes)}

    async def list_rooms_async(self, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        # 인증된 사용자의 방 목록만 반환한다 (스코핑 키는 요청값이 아니라 토큰의 user_id)
        user_id = self._require_authenticated_user_id(authorization)
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT room_id, thread_id, title, model, reasoning_effort FROM chat_room WHERE user_id = %s ORDER BY updated_at DESC", (user_id,))
            room_row_list = await cursor.fetchall()
        return {"rooms" : [dict(room_row) for room_row in room_row_list]}

    async def upsert_room_async(self, room_request : RoomUpsertRequest, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        # 방 생성/갱신 : 소유자는 토큰의 user_id 로 강제한다 (요청 본문의 user_id 는 무시). 남의 방(room_id) 갈취 방지
        user_id = self._require_authenticated_user_id(authorization)
        await self._assert_thread_accessible_async(user_id, room_request.thread_id)
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute(
                "INSERT INTO chat_room (room_id, user_id, thread_id, title, model, reasoning_effort) VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (room_id) DO UPDATE SET thread_id = EXCLUDED.thread_id, title = EXCLUDED.title, model = EXCLUDED.model, "
                "reasoning_effort = EXCLUDED.reasoning_effort, updated_at = NOW() "
                "WHERE chat_room.user_id = EXCLUDED.user_id",
                (room_request.room_id, user_id, room_request.thread_id, room_request.title, room_request.model, room_request.reasoning_effort))
            if cursor.rowcount == 0:
                raise HTTPException(status_code = 403, detail = "ROOM ACCESS DENIED")
        return {"status" : "ok"}

    async def delete_room_async(self, room_id : str, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        # 목록에서만 제거한다 (체크포인트 대화 원본은 retention 배치가 유휴 기준으로 정리). 본인 소유 방만 삭제 가능
        user_id = self._require_authenticated_user_id(authorization)
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute("DELETE FROM chat_room WHERE room_id = %s AND user_id = %s", (room_id, user_id))
            if cursor.rowcount == 0:
                raise HTTPException(status_code = 404, detail = f"ROOM NOT FOUND : {room_id}")
        return {"status" : "deleted"}

    ##################################################
    # 북마크 (답변 단위 · chat_bookmark 테이블)
    ##################################################

    async def list_bookmarks_async(self, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        # 인증된 사용자의 북마크만 최신순으로 반환한다 (스코핑 키는 요청값이 아니라 토큰의 user_id)
        user_id = self._require_authenticated_user_id(authorization)
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT bookmark_id, room_id, agent_index, text, memo, "
                "       (EXTRACT(EPOCH FROM completed_at) * 1000)::BIGINT AS completed_at, "
                "       (EXTRACT(EPOCH FROM created_at)   * 1000)::BIGINT AS created_at "
                "FROM chat_bookmark WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
            bookmark_row_list = await cursor.fetchall()
        return {"bookmarks" : [dict(bookmark_row) for bookmark_row in bookmark_row_list]}

    @staticmethod
    def _normalize_bookmark_memo(memo : Optional[str]) -> Optional[str]:
        # 메모 정규화 : 앞뒤 공백 제거 후 빈 문자열은 NULL(메모 없음)로, 그 외는 최대 길이로 자른다
        if memo is None:
            return None
        trimmed_memo = memo.strip()
        if not trimmed_memo:
            return None
        return trimmed_memo[:ServerApplication.BOOKMARK_MEMO_MAXIMUM_LENGTH]

    async def upsert_bookmark_async(self, bookmark_request : BookmarkUpsertRequest, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        # 북마크 추가 : 소유자는 토큰의 user_id 로 강제한다. 남의 방에는 북마크할 수 없다.
        user_id = self._require_authenticated_user_id(authorization)
        if bookmark_request.agent_index < 0:
            raise HTTPException(status_code = 400, detail = "INVALID AGENT INDEX")
        completed_at_second = (bookmark_request.completed_at / 1000) if bookmark_request.completed_at else None
        memo_text           = ServerApplication._normalize_bookmark_memo(bookmark_request.memo)
        async with self.checkpoint_connection_pool.connection() as connection:
            # 방 소유권 확인 : 본인 소유가 아니면(또는 없는 방이면) INSERT 대상 자체가 없다
            cursor = await connection.execute("SELECT 1 FROM chat_room WHERE room_id = %s AND user_id = %s", (bookmark_request.room_id, user_id))
            if await cursor.fetchone() is None:
                raise HTTPException(status_code = 403, detail = "ROOM ACCESS DENIED")
            # 같은 답변을 다시 북마크하면 미리보기 스냅샷만 갱신한다 (중복 행을 만들지 않는다)
            # 메모는 COALESCE 로 보존한다 — 캐시 재등록처럼 메모를 싣지 않은 요청이 기존 메모를 지우면 안 된다
            await connection.execute(
                "INSERT INTO chat_bookmark (bookmark_id, user_id, room_id, agent_index, text, completed_at, memo) "
                "VALUES (%s, %s, %s, %s, %s, TO_TIMESTAMP(%s), %s) "
                "ON CONFLICT (room_id, agent_index) DO UPDATE SET bookmark_id = EXCLUDED.bookmark_id, text = EXCLUDED.text, "
                "completed_at = EXCLUDED.completed_at, memo = COALESCE(EXCLUDED.memo, chat_bookmark.memo)",
                (bookmark_request.bookmark_id, user_id, bookmark_request.room_id, bookmark_request.agent_index,
                 bookmark_request.text[:500], completed_at_second, memo_text))
        return {"status" : "ok"}

    async def update_bookmark_memo_async(self, bookmark_id : str, memo_request : BookmarkMemoUpdateRequest,
                                         authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        # 메모 수정 : 본인 소유 북마크만 수정 가능. 빈 문자열/누락이면 메모를 지운다(NULL).
        user_id   = self._require_authenticated_user_id(authorization)
        memo_text = ServerApplication._normalize_bookmark_memo(memo_request.memo)
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute(
                "UPDATE chat_bookmark SET memo = %s WHERE bookmark_id = %s AND user_id = %s", (memo_text, bookmark_id, user_id))
            if cursor.rowcount == 0:
                raise HTTPException(status_code = 404, detail = f"BOOKMARK NOT FOUND : {bookmark_id}")
        return {"status" : "ok", "bookmark_id" : bookmark_id, "memo" : memo_text}

    async def delete_bookmark_async(self, bookmark_id : str, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        # 본인 소유 북마크만 삭제 가능. 이미 없으면 404 대신 성공으로 처리한다 (토글 연타/낙관적 UI 재시도 대비)
        user_id = self._require_authenticated_user_id(authorization)
        async with self.checkpoint_connection_pool.connection() as connection:
            await connection.execute("DELETE FROM chat_bookmark WHERE bookmark_id = %s AND user_id = %s", (bookmark_id, user_id))
        return {"status" : "deleted"}

    async def get_api_client_page_async(self) -> FileResponse:
        # 새 창(/dev/api-client)으로 여는 API 테스트 페이지 : 백엔드가 직접 서빙하므로 origin = API 베이스 (CORS 불필요)
        frontend_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "public", "legacy", "api_client.html")
        if not os.path.isfile(frontend_file_path):
            raise HTTPException(status_code = 404, detail = f"API CLIENT PAGE NOT FOUND : {frontend_file_path}")
        return FileResponse(frontend_file_path, media_type = "text/html")

    async def get_redis_snapshot_async(self, thread_id : str, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        # 디버그 패널용 : 해당 스레드와 관련된 Redis 키를 실시간 스냅샷으로 반환한다
        # (런 청크 버퍼 키 형식 : orch:{thread_id}:run:{run_id}:chunk_list)
        user_id = self._require_authenticated_user_id(authorization)
        await self._assert_thread_accessible_async(user_id, thread_id)
        redis_client = self.orchestrator_redis_client
        def try_parse_json(raw_value):
            text = _to_text(raw_value)
            try:
                return json.loads(text)
            except Exception:
                return text
        try:
            matched_key_list = []
            async for key_value in redis_client.scan_iter(match = f"*{thread_id}*", count = 200):
                matched_key_list.append(_to_text(key_value))
                if len(matched_key_list) >= 50:   # 디버그 표시용 상한
                    break
            key_snapshot_list = []
            for key_name in sorted(matched_key_list):
                key_type = _to_text(await redis_client.type(key_name))
                ttl_second_count = await redis_client.ttl(key_name)
                if key_type == "list":
                    total_length = await redis_client.llen(key_name)
                    value = [try_parse_json(item) for item in await redis_client.lrange(key_name, -30, -1)]   # 최근 30개만
                elif key_type == "hash":
                    total_length = await redis_client.hlen(key_name)
                    value = {_to_text(field) : try_parse_json(item) for field, item in (await redis_client.hgetall(key_name)).items()}
                elif key_type == "string":
                    total_length = 1
                    value = try_parse_json(await redis_client.get(key_name))
                else:
                    total_length = None
                    value = f"(미지원 타입 : {key_type})"
                key_snapshot_list.append({"key" : key_name, "type" : key_type, "ttl_second" : ttl_second_count, "length" : total_length, "value" : value})
            return {"thread_id" : thread_id, "matched_key_count" : len(matched_key_list), "keys" : key_snapshot_list}
        except Exception as exception:
            raise HTTPException(status_code = 502, detail = f"REDIS SNAPSHOT FAILED : {exception}")

    async def truncate_thread_async(self, thread_id : str, truncate_request : TruncateThreadRequest, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        # 특정 사용자 질문(0-based 순번)부터 이후 메시지를 체크포인트에서 제거한다.
        # RemoveMessage 를 add_messages 리듀서에 흘려보내 해당 메시지들을 상태에서 지운다.
        user_id = self._require_authenticated_user_id(authorization)
        await self._assert_thread_accessible_async(user_id, thread_id)
        if truncate_request.keep_human_message_count < 0:
            raise HTTPException(status_code = 400, detail = "INVALID KEEP HUMAN MESSAGE COUNT")
        runnable_configuration = {"configurable" : {"thread_id" : thread_id}}
        compiled_graph         = self._get_or_create_compiled_graph(None, None)
        state_snapshot         = await compiled_graph.aget_state(runnable_configuration)
        message_list           = state_snapshot.values.get("messages", []) if state_snapshot else []

        human_message_seen_count = 0
        cut_index                = None
        for message_index, message in enumerate(message_list):
            if isinstance(message, HumanMessage):
                if human_message_seen_count == truncate_request.keep_human_message_count:
                    cut_index = message_index
                    break
                human_message_seen_count += 1
        if cut_index is None:
            # 체크포인트에 그만큼의 사용자 메시지가 없다 (실패/중단 턴으로 프론트와 어긋난 경우) → 제거할 것 없음
            print(f"THREAD TRUNCATE SKIPPED : THREAD {thread_id} - KEEP {truncate_request.keep_human_message_count} - HUMAN {human_message_seen_count}", flush = True)
            return {"thread_id" : thread_id, "kept_count" : len(message_list), "removed_count" : 0}

        removal_message_list = [RemoveMessage(id = message.id) for message in message_list[cut_index:] if getattr(message, "id", None) is not None]
        if removal_message_list:
            await compiled_graph.aupdate_state(runnable_configuration, {"messages" : removal_message_list})

        # 잘려나간 답변들의 북마크를 정리한다. agent_index 는 위치 기반이라 절단 후 남겨두면 엉뚱한 답변을 가리키게 된다.
        # 남길 개수는 get_thread_messages_async 의 표시 규칙과 동일하게 센다 (본문 없는 도구 호출 AI 메시지는 제외).
        kept_agent_message_count = sum(
            1 for message in message_list[:cut_index]
            if type(message).__name__ in ("AIMessage", "AIMessageChunk") and _extract_message_texts(message)[0])
        async with self.checkpoint_connection_pool.connection() as connection:
            await connection.execute(
                "DELETE FROM chat_bookmark WHERE agent_index >= %s AND room_id IN "
                "(SELECT room_id FROM chat_room WHERE thread_id = %s AND user_id = %s)",
                (kept_agent_message_count, thread_id, user_id))

        # 요약도 초기화한다 — 잘려나간 대화를 요약이 계속 가리키면 모델이 삭제된 내용을 기억한 것처럼 답한다.
        # (다음 턴에 남은 히스토리로 다시 요약이 만들어진다)
        if self.conversation_summary_repository is not None:
            await self.conversation_summary_repository.clear_summary_async(thread_id)
        print(f"THREAD TRUNCATED : THREAD {thread_id} - KEPT {cut_index} - REMOVED {len(removal_message_list)}", flush = True)
        return {"thread_id" : thread_id, "kept_count" : cut_index, "removed_count" : len(removal_message_list)}

    async def get_thread_messages_async(self, thread_id : str, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        # 대화 내용 복원 : LangGraph 체크포인트(messages 채널)를 표시용 [{role, text, reasoning}] 으로 변환한다
        user_id = self._require_authenticated_user_id(authorization)
        await self._assert_thread_accessible_async(user_id, thread_id)
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

    async def diagnose_thread_async(self, thread_id : str, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        # ① 순수 체크포인트 로드 시간 : aget_state 전후를 perf_counter 로 측정한다
        user_id = self._require_authenticated_user_id(authorization)
        await self._assert_thread_accessible_async(user_id, thread_id)
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

    @staticmethod
    def _summarize_stream_error(exception : Exception) -> str:
        # 스트리밍 중 발생한 예외를 한 줄로 요약한다 (google ClientError 는 code/message 속성을 활용).
        # 클라이언트 개발자 모드에서 그대로 노출되므로 원인(429 quota, 401 등)이 드러나야 한다.
        status_code    = getattr(exception, "code", None) or getattr(exception, "status_code", None)
        detail_message = getattr(exception, "message", None) or str(exception)
        detail_message = " ".join(str(detail_message).split())[:400]   # 개행/중복 공백 정규화 + 길이 제한
        error_prefix   = f"[{type(exception).__name__}"
        if status_code is not None:
            error_prefix += f" {status_code}"
        error_prefix += "]"
        return f"{error_prefix} {detail_message}"

    async def _append_run_chunk_async(self, thread_id : str, run_id : str, chunk_dictionary : Dict[str, Any]) -> None:
        # 베스트 에포트 : Redis 가 없거나 실패해도 응답 스트리밍을 절대 막지 않는다 (실패 시 이후 버퍼링 비활성화)
        # 오케스트레이터와 동일한 redis_chunk_buffer 를 공유한다
        if self.is_run_buffer_disabled:
            return
        try:
            await self.redis_chunk_buffer.append_chunk_async(thread_id, run_id, chunk_dictionary)
        except Exception as exception:
            self.is_run_buffer_disabled = True
            print(f"RUN BUFFER DISABLED : REDIS UNAVAILABLE - {exception}", flush = True)

    async def _compress_context_if_needed_async(self, thread_id : str, model_name : Optional[str], reasoning_effort : Optional[str]) -> CompressionResult:
        # 체크포인트의 전체 히스토리를 재료로 요약을 갱신한다. 압축 실패가 대화를 막으면 안 되므로
        # 어떤 예외든 "압축 안 함"으로 떨어뜨리고 본 스트리밍은 그대로 진행시킨다.
        if self.conversation_summarizer is None or not self.compression_configuration.is_enabled:
            return CompressionResult.create_uncompressed()
        try:
            state_snapshot = await self._get_or_create_compiled_graph(model_name, reasoning_effort).aget_state({"configurable" : {"thread_id" : thread_id}})
            message_list   = state_snapshot.values.get("messages", []) if state_snapshot else []
            if not message_list:
                return CompressionResult.create_uncompressed()
            # 요약 전용 모델 : 본 대화와 같은 설정을 쓰되 생각(reasoning)을 끄고 생성 상한을 낮춘다.
            # ModelConfiguration 은 frozen dataclass 라 속성 대입이 아니라 replace 로 사본을 만든다.
            summary_model_configuration = dataclasses.replace(
                self._resolve_model_configuration(model_name, None),
                reasoning_enabled   = False,
                reasoning_effort    = None,
                maximum_token_count = self.compression_configuration.summary_maximum_token_count
            )
            summary_chat_model = ChatModelFactory.create(summary_model_configuration)
            return await self.conversation_summarizer.compress_if_needed_async(thread_id, message_list, summary_chat_model)
        except Exception as exception:
            print(f"CONTEXT COMPRESSION SKIPPED : THREAD {thread_id} - {exception}", flush = True)
            return CompressionResult.create_uncompressed()

    @staticmethod
    def _parse_referenced_agent_index(referenced_message_id : str) -> Optional[int]:
        # "agent-3" → 3. 형식이 어긋나면 None 을 돌려주고 호출부가 조용히 건너뛴다.
        if not isinstance(referenced_message_id, str):
            return None
        if not referenced_message_id.startswith(ServerApplication.REFERENCED_MESSAGE_ID_PREFIX):
            return None
        index_text = referenced_message_id[len(ServerApplication.REFERENCED_MESSAGE_ID_PREFIX):]
        if not index_text.isdigit():
            return None
        return int(index_text)

    async def _collect_referenced_message_list_async(self, thread_id : str, referenced_message_id_list : List[str]) -> List[Dict[str, Any]]:
        # 요청받은 답변 ID 들을 체크포인트 본문으로 바꿔 돌려준다.
        #
        # 유효하지 않은 ID(형식 오류·이미 사라진 순번)는 예외를 던지지 않고 건너뛴다.
        # 질문 수정으로 대화가 잘리거나 다른 기기에서 방을 지우면 프론트가 들고 있던 순번이 실제로 없어질 수 있는데,
        # 그때 질문 전체를 실패시키면 사용자는 이유를 알 수 없는 오류만 보게 된다.
        requested_index_list = []
        for referenced_message_id in referenced_message_id_list[:ServerApplication.REFERENCED_MESSAGE_MAXIMUM_COUNT]:
            agent_index = ServerApplication._parse_referenced_agent_index(referenced_message_id)
            if agent_index is None or agent_index in requested_index_list:
                continue
            requested_index_list.append(agent_index)
        if not requested_index_list:
            return []

        try:
            state_snapshot = await self._get_or_create_compiled_graph(None, None).aget_state({"configurable" : {"thread_id" : thread_id}})
        except Exception as exception:
            # 체크포인트를 못 읽어도 질문 자체는 진행시킨다 (참조만 빠진다)
            print(f"REFERENCED MESSAGE LOOKUP FAILED : THREAD {thread_id} - {exception}", flush = True)
            return []

        # 표시용 순번과 같은 규칙으로 답변만 추린다 (get_thread_messages_async 와 동일 : 본문 없는 도구 호출 메시지는 제외)
        agent_text_list = []
        for message in (state_snapshot.values.get("messages", []) if state_snapshot else []):
            if type(message).__name__ not in ("AIMessage", "AIMessageChunk"):
                continue
            body_text, _reasoning_text = _extract_message_texts(message)
            if body_text:
                agent_text_list.append(body_text)

        # 사용자가 고른 순서가 아니라 대화 순서대로 넣는다 — 모델이 시간 흐름대로 읽는 편이 자연스럽다
        referenced_message_list = []
        for agent_index in sorted(requested_index_list):
            if agent_index >= len(agent_text_list):
                continue
            referenced_message_list.append({
                "agent_index" : agent_index,
                "text"        : agent_text_list[agent_index][:ServerApplication.REFERENCED_MESSAGE_MAXIMUM_LENGTH]
            })
        return referenced_message_list

    @staticmethod
    def _build_referenced_context_block(referenced_message_list : List[Dict[str, Any]]) -> str:
        # 통째로 고른 답변들을 <referenced_context> 태그로 묶는다.
        # 태그로 감싸는 이유 : 질문 본문과 참조 자료의 경계를 모델이 확실히 구분하게 하려는 것이다.
        if not referenced_message_list:
            return ""
        block_line_list = ["<referenced_context>"]
        for referenced_message in referenced_message_list:
            block_line_list.append(f"[답변 #{referenced_message['agent_index'] + 1}]")
            block_line_list.append(referenced_message["text"])
        block_line_list.append("</referenced_context>")
        return "\n".join(block_line_list)

    @staticmethod
    def _build_referenced_message_text(message : str, referenced_text : Optional[str], referenced_context_block : str = "") -> str:
        # 참조가 있으면 <referenced_context>(답변 통째로) → [참조 내용](드래그 발췌) → [질문] 순으로 조합한다.
        # 조합 결과를 그대로 HumanMessage 로 저장하는 이유 : 다음 턴에도 체크포인트에서 참조 맥락이 함께 복원되어야
        # "아까 그거"처럼 발췌를 가리키는 후속 질문이 이어진다.
        trimmed_reference = (referenced_text or "").strip()
        if not trimmed_reference and not referenced_context_block:
            return message

        composed_section_list = []
        if referenced_context_block:
            composed_section_list.append(referenced_context_block)
        if trimmed_reference:
            composed_section_list.append(f"[참조 내용]: {trimmed_reference[:ServerApplication.REFERENCED_TEXT_MAXIMUM_LENGTH]}")
        composed_section_list.append(f"[질문]: {message}")
        return "\n".join(composed_section_list)

    async def stream_async(self, stream_request : StreamRequest, authorization : Optional[str] = Header(None)) -> StreamingResponse:
        # 인증 + 스레드 소유권 검증 : 남의 스레드로 스트리밍(대화 이어쓰기) 방지
        user_id = self._require_authenticated_user_id(authorization)
        await self._assert_thread_accessible_async(user_id, stream_request.thread_id)
        # 이번 턴(그래프 1회 실행)을 식별하는 run_id 를 발급한다.
        # 오케스트레이터(GraphStreamExecutor)와 동일하게 configurable.run_id 로 그래프에 전달하고,
        # 청크를 orch:{thread_id}:run:{run_id}:chunk_list 버퍼에 누적해 디버그 패널에서 추적할 수 있게 한다.
        run_id                 = str(uuid.uuid4())
        runnable_configuration = {"configurable" : {"thread_id" : stream_request.thread_id, "run_id" : run_id}}
        # 우클릭으로 고른 이전 답변들을 체크포인트에서 찾아 <referenced_context> 로 묶는다 (없는 ID 는 조용히 빠진다)
        referenced_message_list  = await self._collect_referenced_message_list_async(stream_request.thread_id, stream_request.referenced_message_id_list)
        referenced_context_block = ServerApplication._build_referenced_context_block(referenced_message_list)
        composed_message_text    = ServerApplication._build_referenced_message_text(
            stream_request.message, stream_request.referenced_text, referenced_context_block)
        # 이미지가 붙어 있으면 멀티모달 content 블록으로, 없으면 지금까지처럼 문자열 그대로 넘긴다.
        # (인라인 모드에서는 스토리지에서 이미지를 내려받으므로 블로킹 I/O 를 스레드로 뺀다)
        composed_message_content = await asyncio.to_thread(
            self.vision_message_builder.build_message_content, composed_message_text, stream_request.image_url_list)
        input_dictionary         = {"messages" : [HumanMessage(content = composed_message_content)]}
        compiled_graph         = self._get_or_create_compiled_graph(stream_request.model, stream_request.reasoning_effort)

        # 대화 압축 : astream 이전에 요약을 만들어 chat_room 에 저장해 둔다.
        # 그래야 그래프 안의 ContextCompressionMiddleware 가 방금 갱신된 요약을 읽어 프롬프트를 재구성한다.
        compression_result = await self._compress_context_if_needed_async(stream_request.thread_id, stream_request.model, stream_request.reasoning_effort)

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
            print(f"STREAM START : THREAD {stream_request.thread_id} - RUN {run_id} - MODEL {stream_request.model or self._get_default_model_key()} - EFFORT {stream_request.reasoning_effort or 'default'}", flush = True)
            # 첫 이벤트로 run_id 를 알린다 (클라이언트가 이번 턴을 식별/추적할 수 있게)
            if stream_request.include_reasoning:
                yield json.dumps({"type" : "start", "run_id" : run_id, "thread_id" : stream_request.thread_id}, ensure_ascii = False) + "\n"
                # 압축이 일어난 턴에만 compressed_info 를 알린다 (평문 스트림 모드에서는 본문을 오염시키므로 생략)
                if compression_result.is_compressed:
                    compressed_info_dictionary = CompressedInfoResponse(**compression_result.to_response_dictionary()).model_dump()
                    yield json.dumps({"type" : "compressed_info", "compressed_info" : compressed_info_dictionary}, ensure_ascii = False) + "\n"
            try:
                async for message_chunk, _metadata in compiled_graph.astream(input_dictionary, runnable_configuration, stream_mode = "messages"):
                    # 생각 과정(reasoning) : 사용자가 대기 시간 동안 진행 상황을 볼 수 있게 실시간 전송한다 (NDJSON 모드 한정)
                    reasoning_text, token_text = extract_chunk_texts(message_chunk)
                    if reasoning_text and stream_request.include_reasoning:
                        await self._append_run_chunk_async(stream_request.thread_id, run_id, {"type" : "reasoning", "text" : reasoning_text})
                        yield json.dumps({"type" : "reasoning", "text" : reasoning_text}, ensure_ascii = False) + "\n"
                    if not token_text:
                        continue
                    if not is_first_token_seen:
                        is_first_token_seen = True
                        # TTFT(Time To First Token) : 첫 "답변" 토큰 기준 (생각 토큰 제외) — 프리필+생각 병목이 여기 숫자로 드러난다
                        print(f"TTFT : THREAD {stream_request.thread_id} - RUN {run_id} - {(time.perf_counter() - request_started_at) * 1000:.0f}ms", flush = True)
                    await self._append_run_chunk_async(stream_request.thread_id, run_id, {"type" : "token", "text" : token_text})
                    yield json.dumps({"type" : "token", "text" : token_text}, ensure_ascii = False) + "\n" if stream_request.include_reasoning else token_text
                print(f"TURN COMPLETED : THREAD {stream_request.thread_id} - RUN {run_id} - TOTAL {(time.perf_counter() - request_started_at) * 1000:.0f}ms", flush = True)
            except Exception as exception:
                # 모델 호출 실패(429 quota, 인증 오류 등) : StreamingResponse 는 이미 200 헤더를 보냈으므로
                # HTTP 상태로 알릴 수 없다 → 스트림 본문에 error 이벤트를 실어 클라이언트가 원인을 표시하게 한다
                error_text = ServerApplication._summarize_stream_error(exception)
                print(f"STREAM ERROR : THREAD {stream_request.thread_id} - RUN {run_id} - {error_text}", flush = True)
                await self._append_run_chunk_async(stream_request.thread_id, run_id, {"type" : "error", "text" : error_text})
                if stream_request.include_reasoning:
                    yield json.dumps({"type" : "error", "text" : error_text}, ensure_ascii = False) + "\n"
                else:
                    yield f"\n[ERROR] {error_text}"

        response_media_type = "application/x-ndjson" if stream_request.include_reasoning else "text/plain; charset=utf-8"
        # X-Run-Id / X-Thread-Id : 스트림 본문을 파싱하지 않고도 이번 턴을 식별할 수 있게 헤더로도 노출한다
        return StreamingResponse(
            generate_token_stream_async(),
            media_type = response_media_type,
            headers    = {"Cache-Control" : "no-cache", "X-Accel-Buffering" : "no", "X-Run-Id" : run_id, "X-Thread-Id" : stream_request.thread_id}
        )

    @asynccontextmanager
    async def lifespan_async(self, fast_api : FastAPI) -> AsyncIterator[None]:
        await self.postgresql_pool_manager.open_async()
        try:
            await self.job_schema_initializer.initialize_schema_async()
            await self.user_schema_initializer.initialize_schema_async()
            await self._initialize_checkpointer_async()
            await self.redis_stream_client.open_async()
            await self.redis_stream_client.ping_async()
            await self.job_reaper.start_async()
            await self.orchestrator_redis_client.ping()
            yield
        finally:
            await self.orchestrator_redis_client.aclose()
            await self.job_reaper.stop_async()
            await self.job_manager.shutdown_async()
            await self.redis_stream_client.close_async()
            if self.checkpoint_connection_pool is not None:
                await self.checkpoint_connection_pool.close()
            await self.postgresql_pool_manager.close_async()

    def get_application(self) -> FastAPI:
        return self.application

if __name__ == "__main__":
    server_application = ServerApplication()
    uvicorn_config     = uvicorn.Config(server_application.get_application(), host = os.getenv("SERVER_HOST", "localhost"), port = int(os.getenv("SERVER_PORT", os.getenv("MONITOR_PORT", "8000"))))
    uvicorn_server     = uvicorn.Server(uvicorn_config)
    if sys.platform == "win32":
        # uvicorn 은 Windows 에서 ProactorEventLoop 를 강제하지만 psycopg 비동기(체크포인터)가
        # 이를 지원하지 않으므로 SelectorEventLoop 팩토리로 직접 구동한다
        asyncio.run(uvicorn_server.serve(), loop_factory = asyncio.SelectorEventLoop)
    else:
        uvicorn_server.run()
