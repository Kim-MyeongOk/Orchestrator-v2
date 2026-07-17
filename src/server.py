import os
import json
import uvicorn

from dotenv        import load_dotenv
from fastapi       import FastAPI
from typing        import Optional
from typing        import Dict
from typing        import Any
from contextlib    import asynccontextmanager
from typing        import AsyncIterator
from redis.asyncio import Redis

from common.database.postgresql.postgresql_pool_manager  import PostgresqlPoolManager
from common.cache.redis_stream.redis_stream_client       import RedisStreamClient
from common.identifier.uuid_v7.uuid_v7_generator         import UUIDV7Generator
from app.llm.job.job_configuration                       import JobConfiguration
from app.llm.repository.job_repository                   import JobRepository
from app.llm.repository.job_message_repository           import JobMessageRepository
from app.llm.repository.job_event_repository             import JobEventRepository
from app.llm.repository.job_chunk_repository             import JobChunkRepository
from app.llm.repository.job_task_repository              import JobTaskRepository
from app.llm.repository.chat_thread_repository           import ChatThreadRepository
from app.llm.repository.thread_message_repository        import ThreadMessageRepository
from app.llm.repository.job_schema_initializer           import JobSchemaInitializer
from app.llm.job.job_transfer.job_transfer               import JobTransfer
from app.llm.job.job_executor.job_executor               import JobExecutor
from app.llm.job.job_manager.job_manager                 import JobManager
from app.llm.job.job_subscription.job_subscription       import JobSubscription
from app.llm.job.job_manager.job_reaper                  import JobReaper
from app.llm.api.llm_api_router                          import LLMAPIRouter
from app.llm.api.chat_api_router                         import ChatAPIRouter
from app.llm.chat.chat_query_service                     import ChatQueryService
from common.database.postgresql.postgresql_configuration import PostgresqlConfiguration
from common.cache.redis_stream.redis_configuration       import RedisConfiguration
from app.llm.agent.model_configuration                   import ModelConfiguration
from app.orchestrator.agent.fake_compiled_graph          import FakeCompiledGraph
from app.orchestrator.api.orchestrator_api_router        import OrchestratorAPIRouter
from app.orchestrator.service.chat_history_service       import ChatHistoryService
from app.orchestrator.service.chunk_flush_service        import ChunkFlushService
from app.orchestrator.service.graph_stream_executor      import GraphStreamExecutor
from app.orchestrator.service.redis_chunk_buffer         import RedisChunkBuffer

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
        self.orchestrator_redis_client = ServerApplication._create_orchestrator_redis_client()
        self.redis_chunk_buffer        = RedisChunkBuffer(self.orchestrator_redis_client)
        self.chat_history_service      = ChatHistoryService(self.job_repository, self.job_message_repository)
        self.chunk_flush_service       = ChunkFlushService(self.postgresql_pool_manager, self.redis_chunk_buffer, self.job_repository, self.job_message_repository, self.chat_thread_repository)
        self.graph_stream_executor     = GraphStreamExecutor(self.redis_chunk_buffer)
        self.orchestrator_api_router   = OrchestratorAPIRouter(FakeCompiledGraph(), self.uuid_v7_generator, self.chat_history_service, self.chunk_flush_service, self.graph_stream_executor, self.redis_chunk_buffer)  # 실제 서비스에서는 workflow.compile() 결과로 교체

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
            await self.postgresql_pool_manager.close_async()

    def get_application(self) -> FastAPI:
        return self.application

if __name__ == "__main__":
    server_application = ServerApplication()
    uvicorn.run(server_application.get_application(), host = os.getenv("SERVER_HOST", "localhost"), port = int(os.getenv("SERVER_PORT", "8000")))
