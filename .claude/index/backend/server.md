파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\server.py`

모듈 기능: 통합 FastAPI 애플리케이션의 **조립 루트(Composition Root)**.
인프라 생성 · 그래프 캐시 · 라우트 등록 · 스트리밍만 남기고, 기능별 로직은 서비스로 위임한다.

> **2026-07-28 리팩토링** : 1263줄 단일 클래스에서 762줄로 줄이고 기능을 도메인별로 분리했다.
> 옮겨간 곳은 아래 "분리된 기능" 표를 참고한다.

## 분리된 기능

| 옮겨간 곳 | 내용 |
|---|---|
| `app/monitor/api/*.py` | 요청/응답 스키마 8종 (Register/Login/RoomUpsert/BookmarkUpsert/BookmarkMemoUpdate/Stream/TruncateThread/CompressedInfo) |
| `app/monitor/service/auth_service.py` | 토큰 발급·검증, 스레드 소유권, 회원가입/로그인 |
| `app/monitor/service/room_service.py` | 채팅방 CRUD |
| `app/monitor/service/bookmark_service.py` | 북마크 CRUD + 메모 정규화 |
| `app/monitor/service/thread_service.py` | 대화 복원 / 절단 / 진단 |
| `app/monitor/service/debug_service.py` | Redis 스냅샷 / API 테스트 페이지 |
| `app/monitor/service/model_catalog_service.py` | 모델 목록 / 프리셋 조회 |
| `app/monitor/service/image_upload_handler.py` | `POST /api/upload` HTTP 검증 계층 |
| `app/llm/reference/reference_context_builder.py` | 참조 발췌·답변 다중 참조 프롬프트 조립 |
| `app/llm/agent/think_token_helper.py` | 생각 토큰 감지/트리밍/본문 추출 |
| `app/llm/agent/think_trimming_middleware.py` | `ThinkTrimmingMiddleware` |
| `app/database/table_query/*_query.py` | 테이블별 DDL + 쿼리 상수 (인라인 SQL 제거) |

## 서비스 조립 시점

DB 풀이 필요한 서비스는 `__init__` 에서 `None` 으로 두고 **`_initialize_checkpointer_async()`(lifespan)** 에서 만든다.
`ModelCatalogService` 만 DB 를 쓰지 않아 `__init__` 에서 생성한다.

`ThreadService` · `ReferenceContextBuilder` 는 그래프 캐시를 직접 받지 않고 **콜러블**(`lambda`)로 받는다 — 순환 의존 방지.

## 라우트 어댑터

`register_user_async()`, `list_rooms_async()`, `upload_image_async()` … 등은 **얇은 어댑터**다.
실제 로직은 서비스가 갖고 있고 여기서는 HTTP 시그니처만 붙여 넘긴다.

> **서비스 메서드를 직접 등록하면 안 된다.** FastAPI 는 등록된 함수의 시그니처를 읽어 의존성을 주입하므로
> (`Header(None)` · `File(...)` 기본값), 그냥 등록하면 `authorization` 이 쿼리 파라미터로 잘못 해석된다.

## server.py 에 남은 것

하위 함수 기능:
- `__init__()`: 인프라(PostgreSQL/Redis/Job/오케스트레이터) 생성, 미들웨어·라우트 등록
- `_get_context_compression_configuration()` / `_get_postgresql_configuration()` /
  `_get_redis_configuration()` / `_get_model_configuration()`: 환경변수 → 설정 객체
- `_create_orchestrator_compiled_graph()` / `_create_orchestrator_redis_client()`: 오케스트레이터 그래프·Redis
- `_get_default_model_key()` / `_resolve_model_configuration()` / `_create_monitor_compiled_graph()` /
  `_get_or_create_compiled_graph()`: 모니터 그래프 (모델·강도별 캐시)
- `_initialize_checkpointer_async()`: 체크포인터 생성 + **테이블 DDL(`TableQueryRegistry` 자동 수집)** + 서비스 조립
- `_summarize_stream_error()`: 스트리밍 예외를 한 줄로 요약 (개발자 모드에 그대로 노출)
- `_append_run_chunk_async()`: Redis 청크 버퍼 누적 (베스트 에포트 — 실패해도 스트리밍을 막지 않는다)
- `_compress_context_if_needed_async()`: 대화 압축 (실패해도 "압축 안 함"으로 떨어뜨리고 진행)
- `stream_async()`: 인증 → 참조 조립 → Vision 멀티모달 조립 → `astream` → NDJSON 스트리밍
- `lifespan_async()` / `get_application()`: 수명주기, 앱 반환
- `_create_legacy_model_configuration()` (모듈 함수): 카탈로그가 없을 때의 `.env` 폴백

## 등록 라우트

| 메서드 | 경로 | 어댑터 → 서비스 |
|---|---|---|
| POST | `/auth/register` · `/auth/login` | `AuthService` |
| GET | `/models` · `/config/presets` | `ModelCatalogService` |
| POST | `/api/upload` | `ImageUploadHandler` |
| POST | `/stream` | `server.py` (스트리밍 본체) |
| GET/POST/DELETE | `/rooms` · `/rooms/{room_id}` | `RoomService` |
| GET/POST/PATCH/DELETE | `/bookmarks` · `/bookmarks/{bookmark_id}` | `BookmarkService` |
| GET/POST | `/threads/{thread_id}/messages` · `/truncate` · `/diagnose` | `ThreadService` |
| GET | `/redis/{thread_id}` · `/dev/api-client` | `DebugService` |
