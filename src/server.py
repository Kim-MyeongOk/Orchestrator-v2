import os
import sys
import json
import asyncio
import uvicorn

# Windows : psycopg 비동기(체크포인터)는 ProactorEventLoop 를 지원하지 않으므로 Selector 정책으로 전환한다
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv        import load_dotenv
from fastapi       import FastAPI
from typing        import Optional
from typing        import Dict
from typing        import Any
from contextlib    import asynccontextmanager
from typing        import AsyncIterator
from redis.asyncio import Redis

from common.database.postgresql.postgresql_pool_manager        import PostgresqlPoolManager
from common.cache.redis_stream.redis_stream_client             import RedisStreamClient
from common.identifier.uuid_v7.uuid_v7_generator               import UUIDV7Generator
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
from app.llm.chat.chat_query_service                           import ChatQueryService
from common.database.postgresql.postgresql_configuration       import PostgresqlConfiguration
from common.cache.redis_stream.redis_configuration             import RedisConfiguration
from app.llm.agent.model_configuration                         import ModelConfiguration
from app.llm.agent.deep_agent_factory                          import DeepAgentFactory
from app.llm.agent.tavily_search_tool_factory                  import TavilySearchToolFactory
from app.llm.agent.research_subagent_factory                   import ResearchSubAgentFactory
from app.llm.agent.binary_storage                              import LocalFileBinaryStorage
from app.llm.agent.image_attachment_interceptor                import ImageAttachmentInterceptor
from app.llm.agent.image_reinjection_middleware                import ImageReinjectionMiddleware
from app.orchestrator.api.orchestrator_api_router              import OrchestratorAPIRouter
from app.orchestrator.repository.checkpoint_schema_initializer import CheckpointSchemaInitializer
from app.orchestrator.service.chat_history_service             import ChatHistoryService
from app.orchestrator.service.chunk_flush_service              import ChunkFlushService
from app.orchestrator.service.graph_stream_executor            import GraphStreamExecutor
from app.orchestrator.service.redis_chunk_buffer               import RedisChunkBuffer

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
        self.orchestrator_redis_client    = ServerApplication._create_orchestrator_redis_client()
        self.redis_chunk_buffer           = RedisChunkBuffer(self.orchestrator_redis_client)
        self.chat_history_service         = ChatHistoryService(self.job_repository, self.job_message_repository)
        self.chunk_flush_service          = ChunkFlushService(self.postgresql_pool_manager, self.redis_chunk_buffer, self.job_repository, self.job_message_repository, self.chat_thread_repository)
        self.graph_stream_executor        = GraphStreamExecutor(self.redis_chunk_buffer)

        # 체크포인트 설정 : 활성 시 lifespan 에서 PostgresSaver 를 만들어 그래프를 재조립·교체한다
        # (AsyncPostgresSaver 는 async 컨텍스트가 필요하므로 생성자에서는 비체크포인트 그래프로 시작)
        self.is_checkpoint_enabled        = ServerApplication._get_boolean("CHECKPOINT_ENABLED", False)
        self.checkpoint_partition_count   = int(os.getenv("CHECKPOINT_PARTITION_COUNT", "8"))
        self.checkpoint_schema_initializer = CheckpointSchemaInitializer(self.postgresql_pool_manager, self.checkpoint_partition_count)
        self.checkpoint_connection_pool   = None  # psycopg AsyncConnectionPool (lifespan 에서 생성/종료)

        # 이미지 격리 파이프라인 : 라우터에서 격리(detach) → 체크포인트에는 참조만 → 모델 직전 재주입(reinject)
        # 이미지 입력이 없는 현재는 전 구간 무비용 패스스루로 동작한다
        self.binary_storage               = LocalFileBinaryStorage(os.getenv("ATTACHMENT_STORAGE_DIRECTORY", "./attachment_storage"))
        self.image_attachment_interceptor = ImageAttachmentInterceptor(self.binary_storage, detach_minimum_byte_count = int(os.getenv("ATTACHMENT_DETACH_MINIMUM_BYTE_COUNT", "4096")))

        self.orchestrator_compiled_graph  = self._create_orchestrator_compiled_graph()
        self.orchestrator_api_router      = OrchestratorAPIRouter(self.orchestrator_compiled_graph, self.uuid_v7_generator, self.chat_history_service, self.chunk_flush_service, self.graph_stream_executor, self.redis_chunk_buffer, self.is_checkpoint_enabled, self.image_attachment_interceptor)

        self.application = FastAPI(title = "LLM Job Service", lifespan = self.lifespan_async)
        self.application.include_router(self.llm_api_router.get_router())
        self.application.include_router(self.chat_api_router.get_router())
        self.application.include_router(self.orchestrator_api_router.get_router())

    @staticmethod
    def _get_boolean(environment_variable_name : str, default_value : bool) -> bool:
        environment_value = os.getenv(environment_variable_name)
        if environment_value is None:
            return default_value
        return environment_value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _get_optional_integer(environment_variable_name : str) -> Optional[int]:
        environment_value = os.getenv(environment_variable_name)
        return int(environment_value) if environment_value not in (None, "") else None

    @staticmethod
    def _get_optional_dictionary(environment_variable_name : str) -> Optional[Dict[str, Any]]:
        environment_value = os.getenv(environment_variable_name)
        if environment_value in (None, ""):
            return None
        value = json.loads(environment_value)
        if not isinstance(value, dict):
            raise ValueError(f"INVALID ENVIRONMENT JSON OBJECT : {environment_variable_name}")
        return value

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
        redis_password = os.getenv("REDIS_PASSWORD")
        return RedisConfiguration(
            host                                = os.getenv("REDIS_HOST", "localhost"),
            port                                = int(os.getenv("REDIS_PORT", "6379")),
            password                            = redis_password if redis_password else None,
            database_index                      = int(os.getenv("REDIS_DATABASE_INDEX", "0")),
            is_cluster                          = ServerApplication._get_boolean("REDIS_IS_CLUSTER", False),
            socket_timeout_second_count         = float(os.getenv("REDIS_SOCKET_TIMEOUT_SECOND_COUNT", "10.0")),
            socket_connect_timeout_second_count = float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT_SECOND_COUNT", "5.0")),
            command_maximum_retry_count         = int(os.getenv("REDIS_COMMAND_MAXIMUM_RETRY_COUNT", "1"))
        )

    @staticmethod
    def _get_model_configuration() -> ModelConfiguration:
        default_header_dictionary = ServerApplication._get_optional_dictionary("MODEL_DEFAULT_HEADERS")
        if default_header_dictionary is not None and not all(isinstance(field_name, str) and isinstance(field_value, str) for field_name, field_value in default_header_dictionary.items()):
            raise ValueError("INVALID MODEL DEFAULT HEADERS : MODEL_DEFAULT_HEADERS")
        return ModelConfiguration(
            provider                  = os.getenv("MODEL_PROVIDER", "openai"),
            model_name                = os.getenv("MODEL_NAME", "gpt-4o-mini"),
            api_key                   = os.getenv("MODEL_API_KEY"),
            base_url                  = os.getenv("MODEL_BASE_URL"),
            temperature               = float(os.getenv("MODEL_TEMPERATURE", "0.0")),
            maximum_token_count       = ServerApplication._get_optional_integer("MODEL_MAXIMUM_TOKEN_COUNT"),
            timeout_second_count      = float(os.getenv("MODEL_TIMEOUT_SECOND_COUNT", "120.0")),
            maximum_retry_count       = int(os.getenv("MODEL_MAXIMUM_RETRY_COUNT", "2")),
            default_header_dictionary = default_header_dictionary,
            extra_body_dictionary     = ServerApplication._get_optional_dictionary("MODEL_EXTRA_BODY")
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

    async def _initialize_checkpointer_async(self) -> None:
        # PostgreSQL 체크포인터 초기화 : 파티션 스키마 선생성 → psycopg 풀 → setup() → 그래프 재조립·교체
        # (선주입된 마이그레이션 버전 덕분에 setup() 은 신규 마이그레이션이 없는 한 no-op 이다)
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

        # 체크포인터가 주입된 그래프로 교체 : 이후 요청부터 thread_id 기반 상태 영속화가 동작한다
        self.orchestrator_compiled_graph            = self._create_orchestrator_compiled_graph(checkpointer = checkpoint_saver)
        self.orchestrator_api_router.compiled_graph = self.orchestrator_compiled_graph

    @staticmethod
    def _create_orchestrator_redis_client() -> Redis:
        # 오케스트레이터 청크 버퍼용 redis.asyncio 클라이언트 (기존 REDIS_* 환경변수 재사용)
        redis_configuration = ServerApplication._get_redis_configuration()
        return Redis(
            host                   = redis_configuration.host,
            port                   = redis_configuration.port,
            db                     = redis_configuration.database_index,
            password               = redis_configuration.password,
            decode_responses       = True,
            socket_timeout         = redis_configuration.socket_timeout_second_count,
            socket_connect_timeout = redis_configuration.socket_connect_timeout_second_count
        )

    @asynccontextmanager
    async def lifespan_async(self, fast_api : FastAPI) -> AsyncIterator[None]:
        await self.postgresql_pool_manager.open_async()
        try:
            await self.job_schema_initializer.initialize_schema_async()
            if self.is_checkpoint_enabled:
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
    uvicorn_config     = uvicorn.Config(server_application.get_application(), host = os.getenv("SERVER_HOST", "localhost"), port = int(os.getenv("SERVER_PORT", "8000")))
    uvicorn_server     = uvicorn.Server(uvicorn_config)
    if sys.platform == "win32":
        # uvicorn 은 Windows 에서 ProactorEventLoop 를 강제하지만 psycopg 비동기(체크포인터)가
        # 이를 지원하지 않으므로 SelectorEventLoop 팩토리로 직접 구동한다
        asyncio.run(uvicorn_server.serve(), loop_factory = asyncio.SelectorEventLoop)
    else:
        uvicorn_server.run()
