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

import os
import sys
import json
import time
import dataclasses
import uuid
import asyncio
import uvicorn

# Windows : psycopg 비동기(체크포인터)는 ProactorEventLoop 를 지원하지 않으므로 Selector 정책으로 전환한다
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv                  import load_dotenv
from fastapi                 import FastAPI
from fastapi                 import File
from fastapi                 import Header
from fastapi                 import UploadFile
from fastapi.responses       import StreamingResponse
from fastapi.responses       import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib              import asynccontextmanager
from typing                  import Any
from typing                  import AsyncIterator
from typing                  import Dict
from typing                  import Optional
from redis.asyncio           import Redis

from langchain_core.messages           import HumanMessage

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
from common.security.auth_secret_helper                        import AuthSecretHelper
from common.security.auth_token_renewal_middleware             import AuthTokenRenewalMiddleware
from app.database.table_query_registry                         import TableQueryRegistry
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
from app.llm.api.model_preset_response                         import ModelPresetsResponse
from app.llm.chat.chat_query_service                           import ChatQueryService
from app.llm.image.image_upload_service                        import ImageUploadService
from app.llm.image.vision_message_builder                      import VisionMessageBuilder
from app.llm.agent.think_trimming_middleware                   import ThinkTrimmingMiddleware
from app.llm.agent.image_stripping_middleware                  import ImageStrippingMiddleware
from app.llm.reference.reference_context_builder               import ReferenceContextBuilder
from app.monitor.api.bookmark_memo_update_request              import BookmarkMemoUpdateRequest
from app.monitor.api.bookmark_upsert_request                   import BookmarkUpsertRequest
from app.monitor.api.compressed_info_response                  import CompressedInfoResponse
from app.monitor.api.login_request                             import LoginRequest
from app.monitor.api.register_request                          import RegisterRequest
from app.monitor.api.room_upsert_request                       import RoomUpsertRequest
from app.monitor.api.stream_request                            import StreamRequest
from app.monitor.api.truncate_thread_request                   import TruncateThreadRequest
from app.monitor.service.auth_service                          import AuthService
from app.monitor.service.bookmark_service                      import BookmarkService
from app.monitor.service.debug_service                         import DebugService
from app.monitor.service.image_upload_handler                  import ImageUploadHandler
from app.monitor.service.model_catalog_service                 import ModelCatalogService
from app.monitor.service.room_service                          import RoomService
from app.monitor.service.thread_service                        import ThreadService
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
# 모니터 그래프용 모델 설정 폴백
##################################################

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


class ServerApplication:

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

        # 기능별 서비스 : DB 풀이 필요해 lifespan(_initialize_checkpointer_async)에서 조립된다
        self.auth_service              = None
        self.room_service              = None
        self.bookmark_service          = None
        self.thread_service            = None
        self.debug_service             = None
        self.image_upload_handler      = None
        self.reference_context_builder = None
        # 모델/프리셋 조회는 DB 를 쓰지 않아 지금 만들 수 있다
        self.model_catalog_service     = None   # model_catalog 확정 후 아래에서 생성

        # 모니터 그래프 캐시 : (모델 키, 생각 강도) → 컴파일 그래프. 체크포인터를 공유하므로 스레드 이력은 설정과 무관하게 이어진다
        self.model_catalog                = ModelCatalog.load_default()   # config/models.yaml (없으면 None → .env 폴백)
        self.model_catalog_service        = ModelCatalogService(self.model_catalog)
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
        # 비전 미지원 모델로 바꾸면, 예전에 붙인 이미지가 체크포인트에 남아 매 턴 재전송되어
        # 400 "this model does not support image input" 으로 그 방이 통째로 막힌다 → 프롬프트에서만 걷어낸다
        if not model_configuration.vision_enabled:
            middleware_list.append(ImageStrippingMiddleware())
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

        # 기능별 서비스 조립 : DB 풀을 쓰는 서비스들이라 풀이 열린 지금 시점에 만든다.
        # (라우트는 __init__ 에서 이미 얇은 어댑터로 등록해 두었고, 어댑터가 이 서비스들을 호출한다)
        self.auth_service     = AuthService(self.user_repository, self.checkpoint_connection_pool,
                                            self.auth_token_secret, self.auth_token_ttl_second_count)
        self.room_service     = RoomService(self.checkpoint_connection_pool, self.auth_service)
        self.bookmark_service = BookmarkService(self.checkpoint_connection_pool, self.auth_service)
        self.thread_service   = ThreadService(self.checkpoint_connection_pool, self.auth_service,
                                              lambda : self._get_or_create_compiled_graph(None, None),
                                              self.conversation_summary_repository)
        self.debug_service    = DebugService(self.orchestrator_redis_client, self.auth_service,
                                             os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.image_upload_handler   = ImageUploadHandler(self.image_upload_service, self.auth_service)
        self.reference_context_builder = ReferenceContextBuilder(
            lambda thread_id : self._get_or_create_compiled_graph(None, None)
                                   .aget_state({"configurable" : {"thread_id" : thread_id}}))

        # 오케스트레이터 그래프 : 기존 동작 보존 — CHECKPOINT_ENABLED 일 때만 체크포인터가 주입된 그래프로 교체
        if self.is_checkpoint_enabled:
            self.orchestrator_compiled_graph            = self._create_orchestrator_compiled_graph(checkpointer = checkpoint_saver)
            self.orchestrator_api_router.compiled_graph = self.orchestrator_compiled_graph

        # 모니터 기본 모델 그래프 선생성 (체크포인터 공유)
        self._get_or_create_compiled_graph(None)

        # 모니터 테이블 DDL : app/database/table_query/*_query.py 에서 자동으로 모아 순서대로 만든다.
        # 테이블을 추가할 때 이 파일을 고칠 필요가 없다 — 쿼리 파일 하나만 만들면 된다.
        # (CREATION_ORDER 로 정렬되므로 외래키가 걸린 테이블도 참조 대상 뒤에 생성된다)
        monitor_table_query_class_list = TableQueryRegistry.load_psycopg_table_query_class_list()
        async with self.checkpoint_connection_pool.connection() as connection:
            for table_query_class in monitor_table_query_class_list:
                await connection.execute(table_query_class.CREATE_TABLE)
        print(f"MONITOR TABLE READY : {[table_query_class.TABLE_NAME for table_query_class in monitor_table_query_class_list]}", flush = True)

    ##################################################
    # 모니터 라우트 핸들러
    ##################################################

    ##################################################
    # 라우트 어댑터
    #
    # 실제 로직은 각 서비스가 갖고 있고 여기서는 HTTP 시그니처만 붙여 넘긴다.
    # FastAPI 는 등록된 함수의 시그니처를 읽어 의존성을 주입하므로(Header/File 기본값),
    # 서비스 메서드를 그대로 등록하면 authorization 이 쿼리 파라미터로 잘못 해석된다.
    ##################################################

    async def register_user_async(self, register_request : RegisterRequest) -> Dict[str, Any]:
        return await self.auth_service.register_user_async(register_request)

    async def login_user_async(self, login_request : LoginRequest) -> Dict[str, Any]:
        return await self.auth_service.login_user_async(login_request)

    async def list_models_async(self) -> Dict[str, Any]:
        return await self.model_catalog_service.list_models_async()

    async def list_model_presets_async(self) -> ModelPresetsResponse:
        return await self.model_catalog_service.list_model_presets_async()

    async def upload_image_async(self, file : UploadFile = File(...), authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        return await self.image_upload_handler.upload_image_async(file, authorization)

    async def list_rooms_async(self, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        return await self.room_service.list_rooms_async(authorization)

    async def upsert_room_async(self, room_request : RoomUpsertRequest, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        return await self.room_service.upsert_room_async(room_request, authorization)

    async def delete_room_async(self, room_id : str, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        return await self.room_service.delete_room_async(room_id, authorization)

    async def list_bookmarks_async(self, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        return await self.bookmark_service.list_bookmarks_async(authorization)

    async def upsert_bookmark_async(self, bookmark_request : BookmarkUpsertRequest, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        return await self.bookmark_service.upsert_bookmark_async(bookmark_request, authorization)

    async def update_bookmark_memo_async(self, bookmark_id : str, memo_request : BookmarkMemoUpdateRequest,
                                         authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        return await self.bookmark_service.update_bookmark_memo_async(bookmark_id, memo_request, authorization)

    async def delete_bookmark_async(self, bookmark_id : str, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        return await self.bookmark_service.delete_bookmark_async(bookmark_id, authorization)

    async def get_thread_messages_async(self, thread_id : str, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        return await self.thread_service.get_thread_messages_async(thread_id, authorization)

    async def truncate_thread_async(self, thread_id : str, truncate_request : TruncateThreadRequest,
                                    authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        return await self.thread_service.truncate_thread_async(thread_id, truncate_request, authorization)

    async def diagnose_thread_async(self, thread_id : str, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        return await self.thread_service.diagnose_thread_async(thread_id, authorization)

    async def get_redis_snapshot_async(self, thread_id : str, authorization : Optional[str] = Header(None)) -> Dict[str, Any]:
        return await self.debug_service.get_redis_snapshot_async(thread_id, authorization)

    async def get_api_client_page_async(self) -> FileResponse:
        return await self.debug_service.get_api_client_page_async()

    ##################################################
    # 스트리밍 (모니터 채팅)
    ##################################################

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

    async def stream_async(self, stream_request : StreamRequest, authorization : Optional[str] = Header(None)) -> StreamingResponse:
        # 인증 + 스레드 소유권 검증 : 남의 스레드로 스트리밍(대화 이어쓰기) 방지
        user_id = self.auth_service.require_authenticated_user_id(authorization)
        await self.auth_service.assert_thread_accessible_async(user_id, stream_request.thread_id)
        # 이번 턴(그래프 1회 실행)을 식별하는 run_id 를 발급한다.
        # 오케스트레이터(GraphStreamExecutor)와 동일하게 configurable.run_id 로 그래프에 전달하고,
        # 청크를 orch:{thread_id}:run:{run_id}:chunk_list 버퍼에 누적해 디버그 패널에서 추적할 수 있게 한다.
        run_id                 = str(uuid.uuid4())
        runnable_configuration = {"configurable" : {"thread_id" : stream_request.thread_id, "run_id" : run_id}}
        # 우클릭으로 고른 이전 답변들을 체크포인트에서 찾아 <referenced_context> 로 묶는다 (없는 ID 는 조용히 빠진다)
        referenced_message_list  = await self.reference_context_builder.collect_referenced_message_list_async(
            stream_request.thread_id, stream_request.referenced_message_id_list)
        referenced_context_block = ReferenceContextBuilder.build_context_block(referenced_message_list)
        composed_message_text    = ReferenceContextBuilder.build_message_text(
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
            # asyncpg 테이블(llm_* + chat_user) DDL — TableQueryRegistry 가 자동 수집한다
            await self.job_schema_initializer.initialize_schema_async()
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
