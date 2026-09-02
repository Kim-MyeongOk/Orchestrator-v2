# vLLM Orchestrator Deep Agent - System Design Document

## 📋 개요

**vLLM Orchestrator Deep Agent**는 사용자의 질문을 입력받아 LLM이 웹 리서치, 사고 과정, 토큰 압축 등의 파이프라인을 거쳐 추론 결과를 실시간 스트리밍으로 반환하는 시스템입니다.

- **핵심**: 사용자 요청 → 체크포인트 복원 → 대화 압축 → LLM 추론 → 실시간 토큰 스트리밍 → 클라이언트 표시

---

## 🔄 사용자 요청 흐름 (End-to-End)

### 1️⃣ **클라이언트 → 백엔드 API 요청**

**엔드포인트**: `POST /stream`

```javascript
// 프론트엔드에서 요청 (예: React)
const response = await fetch('/stream', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer <token>'
  },
  body: JSON.stringify({
    thread_id: 'thread-123',
    message: '한국의 GDP 추이는?',
    model: 'gpt-4o-mini',           // 선택적
    reasoning_effort: 'high',        // 선택적 (low/medium/high)
    include_reasoning: true,         // 생각 과정을 함께 스트림할지
    referenced_text: '앞 답변에서 드래그한 발췌',      // 선택적 (드래그 참조)
    referenced_message_id_list: ['agent-0', 'agent-2']  // 선택적 (우클릭 다중 참조)
  })
});
```

**StreamRequest 모델** (`backend/app/monitor/api/stream_request.py`)
```python
class StreamRequest(BaseModel):
    thread_id         : str
    message           : str
    model             : Optional[str] = None           # 요청별 모델 선택
    reasoning_effort  : Optional[str] = None           # 생각 강도
    include_reasoning : bool          = False          # NDJSON vs 평문 스트림
    referenced_text   : Optional[str] = None           # 답변에서 「참조하기」로 담은 발췌 (최대 2000자)
    referenced_message_id_list : List[str] = []        # 우클릭으로 통째로 담은 답변 ID (최대 10개)
```

**참조 프롬프트 조합** (`ReferenceContextBuilder.build_message_text()`)

참조는 두 종류이며, 있는 것만 순서대로 쌓아 `HumanMessage` 를 만든다. 둘 다 없으면 원본 질문을 그대로 쓴다.

```
<referenced_context>
[답변 #3]
{답변 3 본문}
[답변 #5]
{답변 5 본문}
</referenced_context>
[참조 내용]: {referenced_text}
[질문]: {message}
```

| 종류 | 담는 법 | 필드 | 상한 |
|---|---|---|---|
| 발췌 | 답변 본문을 드래그 → 「참조하기」 | `referenced_text` | 2000자 · 1개 |
| 답변 통째 | 답변 말풍선 우클릭 (토글) | `referenced_message_id_list` | 4000자/건 · 10개 |

**답변 ID 체계** — `agent-{답변 순번(0부터)}`

메시지에 고유 ID가 없어 **스레드 안에서 몇 번째 답변인가**로 가리킨다. 북마크의 `agent_index` 와 같은 규칙이다.
백엔드는 체크포인트의 `messages` 에서 본문 있는 `AIMessage` 만 추린 뒤 그 순번으로 찾는다
(`ReferenceContextBuilder.collect_referenced_message_list_async()`). 표시용 순번을 만드는
`ThreadService.get_thread_messages_async()` 와 같은 필터(`ThinkTokenHelper.extract_message_texts()`)를 공유하므로 양쪽이 어긋나지 않는다.

**유효하지 않은 ID는 예외 없이 건너뛴다.** 형식 오류·범위 초과·중복 모두 조용히 걸러내고 남은 것만 주입한다.
질문 수정으로 대화가 잘리거나 다른 기기에서 방을 지우면 프론트가 들고 있던 순번이 실제로 사라질 수 있는데,
그때 질문 전체를 실패시키면 사용자는 이유를 알 수 없는 오류만 보게 된다.

조합 결과를 그대로 체크포인트에 저장한다 — 다음 턴에도 참조 맥락이 복원되어야 "아까 그거"류 후속 질문이 이어진다.

---

### 2️⃣ **인증 & 스레드 소유권 검증** 
**함수**: `stream_async()` (`backend/server.py`)

```
▶ Authorization 헤더에서 Bearer 토큰 추출
▶ AuthTokenHelper.verify_token() → user_id 검증
▶ _assert_thread_accessible_async() → 사용자가 thread_id 소유권 확인
  (다른 사용자가 소유한 스레드로 접근 시도 → 403 Forbidden)
```

**관련 함수**:
- `AuthService.require_authenticated_user_id()` : 토큰 검증
- `AuthService.assert_thread_accessible_async()` : 소유권 검증
  (`backend/app/monitor/service/auth_service.py`)

---

### 3️⃣ **Run ID 발급 & 설정 준비**

```python
run_id = str(uuid.uuid4())  # 이번 턴 식별자
runnable_configuration = {
    "configurable": {
        "thread_id": stream_request.thread_id,
        "run_id": run_id
    }
}
input_dictionary = {
    "messages": [HumanMessage(content = stream_request.message)]
}
# 그래프는 LangGraph CheckPoint에서 기존 messages를 자동 로드
```

**목적**:
- `run_id`: 이번 턴의 모든 청크를 Redis에 추적
- `thread_id`: PostgreSQL 체크포인트에서 히스토리 복원

---

### 4️⃣ **LLM 그래프 조회 (캐시 or 신규 생성)**

**함수**: `_get_or_create_compiled_graph()` (`backend/server.py`)

```python
cache_key = (model_name, reasoning_effort)  # (gpt-4o-mini, high)

if cache_key not in self.compiled_graph_dictionary:
    # 신규 생성: 모델 설정 → DeepAgentFactory → 미들웨어 적용
    compiled_graph = ServerApplication._create_monitor_compiled_graph(
        self.checkpoint_saver,
        model_configuration,
        context_compression_middleware  # 토큰 압축 미들웨어
    )
    self.compiled_graph_dictionary[cache_key] = compiled_graph

return self.compiled_graph_dictionary[cache_key]
```

**미들웨어 적용 순서**:
1. **ThinkTrimmingMiddleware** (`backend/app/llm/agent/think_trimming_middleware.py`)
   - 모델 호출 직전 생각 토큰(`<think>...</think>`) 제거
   - 체크포인트 원본은 보존 (상태 업데이트는 원본으로)

2. **ContextCompressionMiddleware** (app/llm/compression/)
   - 오래된 메시지를 요약으로 대체해 프롬프트 길이 단축
   - 최근 N개 메시지는 원본 유지

---

### 5️⃣ **대화 압축 (Context Compression)**

**함수**: `_compress_context_if_needed_async()` (`backend/server.py`)

**트리거 조건** (설정):
```python
CONTEXT_COMPRESSION_TRIGGER_MESSAGE_COUNT = 14   # 메시지 수
CONTEXT_COMPRESSION_TRIGGER_TOKEN_COUNT = 3000   # 토큰 수
CONTEXT_COMPRESSION_RECENT_KEEP_COUNT = 10       # 최근 10개는 원본
```

**흐름**:
```
① 체크포인트에서 전체 메시지 로드
② 메시지 수 / 토큰 수 임계치 확인
③ 필요하면 ConversationSummarizer 호출
   └─ 요약 전용 모델 (reasoning 비활성화, max_token 512)
       로 오래된 대화를 요약
④ 요약 + 스냅샷 저장 (PostgreSQL chat_room 테이블)
⑤ 압축 결과를 클라이언트에 NDJSON 이벤트로 전송
```

**응답 예시**:
```json
{"type": "compressed_info", "compressed_info": {
  "is_compressed": true,
  "saved_tokens": 1250,
  "summary": "사용자가 한국의 GDP, 인구 동향, 산업 구조를 묻고... 요약 텍스트..."
}}
```

---

### 6️⃣ **LLM 추론 시작 (astream)**

**함수**: `compiled_graph.astream()` (`backend/server.py`)

```python
async for message_chunk, _metadata in compiled_graph.astream(
    input_dictionary,
    runnable_configuration,
    stream_mode = "messages"
):
    # 청크 단위로 수신 시작
```

**내부 동작**:
```
┌─────────────────────────────────────────┐
│ 1. CheckPoint 로드                       │
│    thread_id → PostgreSQL에서 기존      │
│    messages 채널 복원                   │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 2. 미들웨어 적용 (before_model)         │
│    - 생각 토큰 트리밍                   │
│    - 최근 N개 윈도 적용                 │
│    (체크포인트 상태는 변경 X)            │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 3. LLM API 호출                          │
│    - OpenAI / Ollama / Google 등         │
│    - 모델: gpt-4o-mini / qwen3 등       │
│    - 청크 단위 스트리밍 응답             │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 4. 메시지 청크 파싱                     │
│    - reasoning_content 추출              │
│    - token content 추출                  │
│    - 각각 NDJSON으로 변환                │
└─────────────────────────────────────────┘
```

---

### 7️⃣ **실시간 토큰 스트리밍 (클라이언트로 전송)**

**함수**: `generate_token_stream_async()` (`stream_async()` 내부 중첩 함수)

#### 7-1. NDJSON 모드 (include_reasoning=true)

```python
# 이벤트 1: 시작 신호 (run_id, thread_id)
{"type": "start", "run_id": "uuid", "thread_id": "thread-123"}

# 이벤트 2: 압축 정보 (있을 시)
{"type": "compressed_info", "compressed_info": {...}}

# 이벤트 3-N: 생각 과정 (청크 단위)
{"type": "reasoning", "text": "사용자가 한국 GDP를 묻고 있다..."}
{"type": "reasoning", "text": "최근 통계를 찾아보자..."}

# 이벤트 N+1부터: 답변 토큰 (청크 단위)
{"type": "token", "text": "한국의"}
{"type": "token", "text": " GDP는"}
{"type": "token", "text": " 2024년"}
...

# 에러 발생 시
{"type": "error", "text": "[TimeoutError 504] Request timed out"}
```

#### 7-2. 평문 모드 (include_reasoning=false)

```
한국의 GDP는 2024년...
```
(생각 토큰 없이 답변 토큰만 순차 전송)

---

### 8️⃣ **청크 저장 (Redis 버퍼링)**

**함수**: `_append_run_chunk_async()` (`backend/server.py`)

```python
# 각 청크를 Redis에 실시간 누적
# 키: orch:{thread_id}:run:{run_id}:chunk_list
await self.redis_chunk_buffer.append_chunk_async(
    thread_id = stream_request.thread_id,
    run_id = run_id,
    chunk_dictionary = {
        "type": "token",  # reasoning / token / error
        "text": "한국의"
    }
)
```

**목적**:
- 실시간 스트림 디버깅 (전송된 청크 조회)
- 대화 완료 후 벌크 저장 시 기반 데이터

---

### 9️⃣ **체크포인트 자동 업데이트**

스트리밍 완료 후 LangGraph가 자동으로:

```python
# PostgreSQL langgraph_checkpoint 테이블에 기록
INSERT INTO langgraph_checkpoint (...)
  VALUES (thread_id, channel_id, values, ...)
```

**저장 내용**:
- `messages`: 기존 + 새로운 HumanMessage + AIMessage
- `tools_result`: 도구 호출 결과 (검색 등)
- `state`: 그래프 상태 스냅샷

---

### 🔟 **응답 종료 & 대화 데이터 저장**

**함수**: `generate_token_stream_async()` 완료 후

```python
print(f"TURN COMPLETED : THREAD {thread_id} - RUN {run_id} - TOTAL {elapsed_ms}ms")
```

이후 프론트엔드에서 다음을 수행:
1. Redis 버퍼의 청크 조회 (`GET /redis/{thread_id}`)
2. 대화방 목록 새로고침 (`GET /rooms`)
3. 메시지 히스토리 표시 (`GET /threads/{thread_id}/messages`)

---

## 🗂️ 핵심 컴포넌트별 역할

### Backend 모듈 구조 (2026-07-28 리팩토링)

`server.py` 가 1263줄 단일 클래스로 비대해져 기능별로 분리했다 (**762줄**로 축소).
`server.py` 는 이제 **조립 루트(Composition Root)** 다 — 인프라 생성 · 그래프 캐시 · 라우트 등록 · 스트리밍만 남는다.

```
backend/
  server.py                                  ← 조립 + 라우트 어댑터 + 스트리밍
  app/
    database/                                ← 테이블별 SQL (신설)
      table_query_registry.py                자동 탐색 레지스트리
      table_query/  chat_room_query.py · chat_bookmark_query.py · chat_user_query.py
    monitor/                                 ← 루트 경로 라우트 계열 (신설)
      api/      register_request.py · login_request.py · room_upsert_request.py
                bookmark_upsert_request.py · bookmark_memo_update_request.py
                stream_request.py · truncate_thread_request.py · compressed_info_response.py
      service/  auth_service.py          인증·토큰·스레드 소유권
                room_service.py          채팅방 CRUD
                bookmark_service.py      북마크 CRUD + 메모 정규화
                thread_service.py        대화 복원 / 절단 / 진단
                debug_service.py         Redis 스냅샷 / API 테스트 페이지
                model_catalog_service.py 모델 목록 / 프리셋
                image_upload_handler.py  POST /api/upload HTTP 검증
    llm/
      reference/  reference_context_builder.py   참조 발췌·다중 참조 프롬프트 조립
      agent/      think_token_helper.py          생각 토큰 감지/트리밍/본문 추출
                  think_trimming_middleware.py   ThinkTrimmingMiddleware
```

**서비스 조립 시점** — DB 풀이 필요한 서비스는 `__init__` 에서 `None` 으로 두고
`_initialize_checkpointer_async()`(lifespan)에서 만든다. `ModelCatalogService` 만 DB 를 안 써서 `__init__` 에서 생성한다.

`ThreadService` · `ReferenceContextBuilder` 는 그래프 캐시를 직접 받지 않고 **콜러블(`lambda`)** 로 받는다 — 순환 의존 방지.

**라우트 어댑터가 필요한 이유** — FastAPI 는 등록된 함수의 시그니처를 읽어 의존성을 주입한다
(`Header(None)` · `File(...)` 기본값). 서비스 메서드를 그대로 등록하면 `authorization` 이 **쿼리 파라미터로 잘못 해석**되므로,
`server.py` 에 HTTP 시그니처만 붙인 얇은 어댑터를 두고 서비스로 위임한다.

---

### 테이블 쿼리 : 테이블당 파일 하나

SQL 이 서비스·초기화기·`server.py` 에 흩어져 있어(테이블 하나가 4~5곳) **테이블당 `.py` 파일 하나**로 모았다.

```
app/database/
  table_query_registry.py        ← 자동 탐색 (이 파일은 고칠 일이 없다)
  table_query/
    chat_user_query.py           order=5    asyncpg ($1)   DDL + 쿼리
    chat_room_query.py           order=10   psycopg (%s)   DDL + 쿼리
    chat_bookmark_query.py       order=20   psycopg (%s)   DDL + 쿼리
    llm_job_query.py             order=110  asyncpg ($1)   DDL만
    llm_thread_query.py          order=120  asyncpg ($1)   DDL만
    llm_job_message_query.py     order=130  asyncpg ($1)   DDL만
    llm_thread_message_query.py  order=140  asyncpg ($1)   DDL만
    llm_job_chunk_query.py       order=150  asyncpg ($1)   DDL만
    llm_job_task_query.py        order=160  asyncpg ($1)   DDL만
    llm_job_event_query.py       order=170  asyncpg ($1)   DDL만
```

**DDL 실행 주체는 둘뿐이다.**
- asyncpg(8개) : `JobSchemaInitializer` — `UserSchemaInitializer` 는 하는 일이 같아져 **삭제하고 통합**했다
- psycopg(2개) : `server.py` `_initialize_checkpointer_async()`

**`checkpoints` 계열은 이 규약에서 제외한다.**
`checkpoints` / `checkpoint_blobs` / `checkpoint_writes` / `checkpoint_migrations` 는
**LangGraph 라이브러리(`langgraph-checkpoint-postgres`)의 MIGRATIONS 최종 스키마와 정확히 일치해야 하고**,
파티션 수가 런타임 변수(`CHECKPOINT_PARTITION_COUNT`)라 DDL 이 템플릿이다.
또 `AsyncPostgresSaver.setup()` 이 `CREATE INDEX CONCURRENTLY` 로 파티션 테이블에서 크래시하는 문제를
피하려고 마이그레이션 버전 행을 선주입하는 로직과 한 덩어리다.
따라서 `CheckpointSchemaInitializer` 가 계속 따로 관리한다 — 라이브러리 버전에 종속된 스키마를
"테이블당 파일 하나" 규약으로 끌어오면 업그레이드 때 어긋난다.

**스키마 완비 판정은 세 테이블을 모두 본다** (`REQUIRED_TABLE_NAME_TUPLE`).
`checkpoints` 하나만 확인하면 나머지 둘(`checkpoint_blobs` / `checkpoint_writes`)이 지워진 상태에서도
"완비"로 오판해 통과한다. 그러면 `checkpoint_migrations` 에 버전이 차 있어 마이그레이션도 건너뛰므로
**영원히 복구되지 않고 매 요청이 `UndefinedTable: checkpoint_blobs` 로 실패**한다.
하나라도 빠지면 DDL 을 다시 실행한다 — 전부 `IF NOT EXISTS` 라 남아 있는 테이블은 건드리지 않는다.
```
CHECKPOINT SCHEMA INCOMPLETE : MISSING ['checkpoint_blobs', 'checkpoint_writes'] - RECREATING
```

**새 테이블 추가 = 파일 하나 생성.** 등록 코드를 고칠 필요가 없다 —
`TableQueryRegistry` 가 `pkgutil` 로 `*_query.py` 를 훑어 `TABLE_NAME` + `CREATE_TABLE` 을 가진 클래스를 자동 수집한다.
(목록을 손으로 관리하면 파일을 만들고 등록을 잊는 실수가 반드시 생긴다)

| 속성 | 필수 | 설명 |
|---|---|---|
| `TABLE_NAME` | ✅ | 테이블 이름 |
| `CREATE_TABLE` | ✅ | DDL (CREATE TABLE / INDEX / ALTER 를 함께 넣어도 된다) |
| `CREATION_ORDER` | 권장 | 작은 값이 먼저 생성 — **외래키 참조 순서** (미지정 시 100) |
| `IS_ASYNCPG` | 조건부 | asyncpg 풀이면 `True` (기본 `False` = psycopg) |

DDL 실행 주체 : psycopg 테이블은 `server.py` `_initialize_checkpointer_async()`,
asyncpg 테이블은 `UserSchemaInitializer` 가 각각 레지스트리에서 받아 순서대로 실행한다.
기동 로그에 `MONITOR TABLE READY : [...]` / `ASYNCPG TABLE READY : [...]` 로 찍힌다.

> ⚠️ **풀마다 플레이스홀더가 다르다.** psycopg 는 `%s`, asyncpg 는 `$1, $2` 다. 섞으면 런타임에 터진다.
> `job_*` 테이블은 이미 `app/llm/repository/` 에 테이블별 저장소가 있어 이번 정리 대상에서 제외했다.

---

### Backend (Python)

| 컴포넌트 | 역할 | 경로 |
|---------|------|------|
| **FastAPI Server** | 조립 루트, 라우트 어댑터, 스트리밍 | `backend/server.py` |
| **Monitor Services** | 인증·방·북마크·스레드·디버그·모델·업로드 | `backend/app/monitor/service/` |
| **LangGraph Graph** | 에이전트 상태 관리, 메시지 흐름 | `backend/app/orchestrator/` |
| **DeepAgentFactory** | LLM 에이전트 조립 | `backend/app/llm/agent/` |
| **PostgreSQL CheckPoint** | 대화 히스토리 영구 저장 | `langgraph_checkpoint*` 테이블 |
| **Redis Stream** | 비동기 작업, 청크 버퍼링 | Redis streams |
| **Middleware** | 생각 토큰 트리밍, 대화 압축 | `backend/app/llm/compression/` |

### 이미지 업로드 & Vision 추론 (MinIO)

```
[브라우저] 파일 선택/드롭/붙여넣기
    → POST /api/upload (multipart, 인증 필요)
    → ImageUploadService → s3_helper.upload_fileobj()  →  MinIO  uploads/{uuid}.{ext}
    → presigned URL 발급 → 프론트에 반환 (썸네일 표시)
    → POST /stream { message, image_url_list:[...] }
    → VisionMessageBuilder → [{"type":"text"...},{"type":"image_url"...}] → Vision 모델
```

**boto3 를 직접 호출하지 않는다.** 모든 S3 접근은 `common/storage/s3_helper.py` 의 `s3_helper` 싱글톤을 거친다.

| 환경변수 | 값(예) | 비고 |
|---|---|---|
| `S3_ENDPOINT_URL` | `http://s3.samsung.com:9000` | MinIO 엔드포인트 |
| `S3_BUCKET_NAME` | `vision-uploads` | 없으면 최초 업로드 시 자동 생성 시도 |
| `S3_USE_SSL` / `S3_REGION_NAME` | `false` / `us-east-1` | |
| `S3_PUBLIC_DOMAIN` | `http://s3.samsung.com:9000/vision-uploads` | ⚠️ **미설정 시 `get_public_https_url()` 이 AWS 주소를 만든다** |
| `IMAGE_URL_MODE` | `presigned` | `public` 은 버킷 공개 읽기 필요 |
| `IMAGE_PRESIGNED_EXPIRATION_SECOND_COUNT` | `86400` | Lifecycle 만료(1일)보다 길게 두면 링크만 살고 객체는 사라진다 |
| `VISION_IMAGE_INLINE_BASE64` | `false` | `true` 면 URL 대신 base64 인라인 (**Ollama 용**) |

**모델별 이미지 전달 방식이 다르다.**
vLLM · OpenAI 규격은 URL 을 서버가 직접 내려받지만, **Ollama 는 URL 을 읽지 못하고 base64 를 요구한다.**
후자는 `VISION_IMAGE_INLINE_BASE64=true` 로 두면 MinIO 에서 내려받아 `data:` URI 로 바꿔 넣는다.

**Lifecycle (24시간 자동 삭제)** — MinIO CLI 로 설정한다. `mc` 는 `tools/mc.exe` 에 두었다(gitignore 대상).
```bash
tools\mc.exe alias set myminio http://s3.samsung.com:9000 <ACCESS_KEY> <SECRET_KEY>
tools\mc.exe ilm rule add --expire-days 1 myminio/vision-uploads
tools\mc.exe ilm rule ls  myminio/vision-uploads          # 확인
```
> 최신 `mc` 는 `ilm add --expiry-days` 가 아니라 **`ilm rule add --expire-days`** 다 (구 문법은 동작하지 않는다).

**모델별 이미지 전달 — 확인된 사실**
`langchain_ollama` 는 `image_url` 의 `data:` URI 를 콤마 기준으로 잘라 Ollama `images[]` 로 넘긴다.
같은 파일에 `"Image data only supported through in-line base64 format."` 이 있어 **URL 모드는 Ollama 에서 동작하지 않는다.**
따라서 Ollama Vision 모델을 쓸 때 `VISION_IMAGE_INLINE_BASE64=true` 는 선택이 아니라 필수다.

**기동 시 스토리지 확인** — `load_dotenv()` 는 이미 설정된 환경변수를 덮어쓰지 않는다.
터미널에 남은 `S3_ENDPOINT_URL` 이 `.env` 를 이겨 목 서버를 바라봐도 업로드는 200 으로 성공하므로 눈치채기 어렵다.
그래서 기동 로그에 실제 대상을 남긴다.
```
S3 STORAGE : endpoint=http://s3.samsung.com:9000 bucket=vision-uploads use_ssl=False url_mode=presigned prefix=uploads
VISION IMAGE MODE : inline_base64=True
```

> 기존 `ImageAttachmentInterceptor`(base64 격리 → 로컬 파일)는 **오케스트레이터 그래프 전용**이며
> 이번 MinIO 경로와는 별개다. 이쪽은 채팅(`/stream`) 경로에서 URL 을 그대로 전달한다.

---

### 회원가입 / 로그인

| 엔드포인트 | 성공 | 실패 |
|---|---|---|
| `POST /auth/register` | `200` + `{user_id, token, status:"registered"}` | `409` 중복 ID · `400` 검증 실패 |
| `POST /auth/login` | `200` + `{user_id, token, status:"ok"}` | `401` ID 없음/비밀번호 불일치 (동일 응답) |

**중복 ID 판정은 `INSERT ... ON CONFLICT (user_id) DO NOTHING RETURNING TRUE` 의 결과로 한다.**
"조회해서 없으면 삽입"이 아니라 한 문장으로 처리하므로, 같은 ID 로 동시에 가입 요청이 들어와도 한쪽만 성공한다.

```json
// 409 Conflict
{ "detail": "이미 등록된 유저입니다." }
```

응답에 `user_id` 를 되싣지 않는다 — 가입 API 를 두드려 계정 존재 여부를 캐낼 수 없게 하기 위함이다.
같은 이유로 로그인 실패는 ID 없음과 비밀번호 불일치를 구분하지 않고 모두 `401` 로 답한다.

프론트(`legacy/login.html`)는 `409` 를 받으면 공용 메시지 줄이 아니라 **ID 입력칸 아래**에 안내를 붙이고
테두리를 붉게 바꾼다. ID 를 고치기 시작하거나 탭을 전환하면 걷힌다.

---

### 인증 (무상태 HMAC 토큰)

`Authorization: Bearer <token>` 헤더 방식이며 쿠키를 쓰지 않는다. 따라서 CORS `allow_credentials` 는 켜지 않는다.

**비밀키는 반드시 고정되어야 한다.** 서명 키가 바뀌면 발급해 둔 토큰이 전부 검증에 실패해 전원 로그아웃된다.
`AuthSecretHelper.resolve_secret()` 이 `환경변수 > 로컬 파일 > 새로 만들어 저장` 순으로 고정 값을 확보한다.

| 설정 | 기본값 | 설명 |
|---|---|---|
| `AUTH_TOKEN_SECRET` | (없으면 파일에서 확보) | 서명 비밀키. **운영에서는 환경변수로 주입** |
| `AUTH_TOKEN_SECRET_FILE_PATH` | `.auth_token_secret` | 개발용 비밀키 파일 (`.gitignore` 대상) |
| `AUTH_TOKEN_TTL_SECOND_COUNT` | `604800` (7일) | 토큰 수명 |
| `CORS_ALLOW_ORIGIN_LIST` | `*` | 쉼표로 구분한 허용 오리진 |

**Silent Refresh (슬라이딩 갱신)** — `AuthTokenRenewalMiddleware`

인증된 요청이 지나갈 때 남은 수명이 절반 아래면 새 토큰을 만들어 `X-Refreshed-Auth-Token` 응답 헤더로 내려준다.
프론트는 이를 받아 저장 토큰을 조용히 교체한다. 이미 만료된 토큰은 되살리지 않는다.

별도 Refresh Token 을 두지 않는 이유 : 무상태 토큰이고 Access/Refresh 를 나눠도 둘 다 같은 localStorage 에
놓여 탈취 위험이 줄지 않는 반면, 갱신 엔드포인트·회전·폐기 관리가 새로 생긴다.

**만료 시 UX** — 401 이면 사유를 남기고 로그인 페이지로 보내되, 작성 중이던 입력은 보존해 재로그인 후 복원한다.

---

### Frontend (React)

| 컴포넌트 | 역할 |
|---------|------|
| **Chat Component** | 메시지 입력, 실시간 스트림 수신 |
| **SSE Reader** | NDJSON 이벤트 파싱 |
| **TTS Engine** | Web Speech API(SpeechSynthesis)로 답변 음성 변환 (`useTTS`) |
| **STT Engine** | Web Speech API(SpeechRecognition)로 음성 받아쓰기 (`useSTT`) |
| **Message Display** | 토큰별 실시간 렌더링 |

**음성 훅(`useTTS` / `useSTT`)은 App 에서 한 번만 생성한다.**
스피커·마이크가 창 전체에 하나뿐이라 컴포넌트마다 만들면 두 세션이 같은 장치를 두고 다툰다.
받아쓰기를 시작하면 TTS 를 먼저 끊는다 — 스피커로 나가는 소리를 마이크가 그대로 받아 적기 때문이다.

STT 결과는 `base(녹음 시작 시점 입력값) + final(확정 누적) + interim(말하는 중)` 세 조각으로 조합한다.
중간 결과는 다음 이벤트에서 더 정확한 문장으로 통째로 대체되므로, 이어 붙이기만 하면
`안녕 / 안녕하세 / 안녕하세요` 처럼 중간 단계가 전부 쌓인다.

---

## 🔌 데이터 흐름 다이어그램

```
┌─────────────┐
│  Frontend   │
│  (React)    │
└──────┬──────┘
       │ POST /stream
       │ {thread_id, message, model}
       ▼
┌─────────────────────────────────────┐
│      Backend (FastAPI)               │
│  stream_async()                     │
├─────────────────────────────────────┤
│ 1. 인증 검증                        │
│ 2. Run ID 발급                      │
│ 3. 그래프 캐시 조회                 │
│ 4. 대화 압축 (필요시)               │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  PostgreSQL CheckPoint              │
│  (LangGraph 상태 저장소)             │
├─────────────────────────────────────┤
│ • thread_id 별 메시지 채널          │
│ • 도구 호출 결과                    │
│ • 요약 정보                         │
└──────┬──────────────────────────────┘
       │ (기존 메시지 복원)
       ▼
┌─────────────────────────────────────┐
│  LangGraph astream()                │
│  (에이전트 실행)                     │
├─────────────────────────────────────┤
│ Middleware:                         │
│  1. 생각 토큰 트리밍               │
│  2. 컨텍스트 압축                   │
│  3. 이미지 재주입                   │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  LLM API (OpenAI / Ollama / etc)    │
│  (모델 추론)                        │
├─────────────────────────────────────┤
│ • 청크 단위 스트리밍                │
│ • reasoning_content 분리            │
└──────┬──────────────────────────────┘
       │ (청크 수신)
       ▼
┌─────────────────────────────────────┐
│  Backend (청크 처리)                │
│  generate_token_stream_async()      │
├─────────────────────────────────────┤
│ • Redis에 청크 누적                 │
│ • NDJSON 이벤트 생성                │
│ • 클라이언트로 스트림 전송          │
└──────┬──────────────────────────────┘
       │ (NDJSON / 평문 스트림)
       ▼
┌─────────────────────────────────────┐
│  Frontend (실시간 수신)             │
│  • 토큰 실시간 렌더링              │
│  • 생각 과정 표시                   │
│  • TTS 음성 변환                    │
└─────────────────────────────────────┘
       │ (턴 완료)
       ▼
┌─────────────────────────────────────┐
│  PostTurn (선택사항)                │
│ • 압축 상태 갱신                    │
│ • 북마크 기록                       │
│ • 방 메타데이터 저장                │
└─────────────────────────────────────┘
```

---

## 📊 주요 성능 지표

### 1️⃣ CheckPoint 로드 시간
**함수**: `ThreadService.diagnose_thread_async()` (`backend/app/monitor/service/thread_service.py`)

```python
load_time_ms = 체크포인트 로드 소요 시간
```

- 병목 지점: 메시지 수 증가, 생각 토큰 누적
- 개선: 토큰 트리밍, 윈도잉, 자동 압축

### 2️⃣ TTFT (Time To First Token)
**기록**: `generate_token_stream_async()`

```python
TTFT = 첫 답변 토큰까지의 시간 (생각 토큰 제외)
= 프리필 + 생각 토큰 병목 + 모델 지연
```

### 3️⃣ 전체 턴 완료 시간
```python
TURN_COMPLETED = astream 시작부터 마지막 토큰까지
```

---

## 🛡️ 보안 & 접근 제어

### 인증 계층
```
요청 → Authorization: Bearer <token>
     → AuthTokenHelper.verify_token()
     → user_id 추출
```

### 스레드 소유권 검증
```
user_id (토큰) vs chat_room.user_id
= 불일치 → 403 Forbidden
```

### 데이터 격리
- 사용자마다 독립적인 `chat_room`, `chat_bookmark` 기록
- 체크포인트는 `thread_id` 기준으로 격리 (LangGraph 내장)

---

## 🔧 개발/디버그 API

### Redis 청크 조회
```bash
GET /redis/{thread_id}
Authorization: Bearer <token>

응답:
{
  "thread_id": "thread-123",
  "matched_key_count": 3,
  "keys": [
    {
      "key": "orch:thread-123:run:uuid:chunk_list",
      "type": "list",
      "length": 45,
      "value": [{"type":"token", "text":"..."}, ...]
    }
  ]
}
```

### 체크포인트 진단
```bash
GET /diagnose?thread_id=thread-123
Authorization: Bearer <token>

응답:
{
  "load_time_ms": 23.5,
  "message_count": 24,
  "think_tag_kb": 127.3
}
```

### 메시지 히스토리 조회
```bash
GET /threads/thread-123/messages
Authorization: Bearer <token>

응답:
{
  "thread_id": "thread-123",
  "messages": [
    {"role": "user", "text": "한국의 GDP는?"},
    {"role": "agent", "text": "한국의 GDP는...", "reasoning": "<think>...</think>"}
  ]
}
```

### 북마크 (답변 단위 · `chat_bookmark` 테이블)

북마크 대상은 "방 안에서 몇 번째 답변인가"(`agent_index`)로 식별한다.
`memo` 는 사용자가 북마크한 답변에 직접 남기는 기록으로, 최대 1000자(`BookmarkService.MEMO_MAXIMUM_LENGTH`)까지 저장한다.

**테이블 스키마** (`backend/app/database/table_query/chat_bookmark_query.py`)
```sql
CREATE TABLE IF NOT EXISTS chat_bookmark
(
    bookmark_id  TEXT        PRIMARY KEY,
    user_id      TEXT        NOT NULL,
    room_id      TEXT        NOT NULL REFERENCES chat_room (room_id) ON DELETE CASCADE,
    agent_index  INTEGER     NOT NULL,
    text         TEXT        NOT NULL DEFAULT '',   -- 목록 미리보기용 스냅샷 (최대 500자)
    completed_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (room_id, agent_index)
);
-- 기존 배포에도 붙어야 하므로 ADD COLUMN IF NOT EXISTS 로 추가한다
ALTER TABLE chat_bookmark ADD COLUMN IF NOT EXISTS memo TEXT;   -- NULL = 메모 없음
```

**엔드포인트**

| 메서드 | 경로 | 핸들러 | 설명 |
|---|---|---|---|
| `GET`    | `/bookmarks`                | `BookmarkService.list_bookmarks_async()`       | 인증 사용자의 북마크 목록 (최신순, `memo` 포함) |
| `POST`   | `/bookmarks`                | `BookmarkService.upsert_bookmark_async()`      | 북마크 추가/갱신. `memo` 가 `null` 이면 기존 메모 보존(`COALESCE`) |
| `PATCH`  | `/bookmarks/{bookmark_id}`  | `BookmarkService.update_bookmark_memo_async()` | **메모만 부분 수정** |
| `DELETE` | `/bookmarks/{bookmark_id}`  | `BookmarkService.delete_bookmark_async()`      | 북마크 삭제 |

```bash
PATCH /bookmarks/{bookmark_id}
Authorization: Bearer <token>
Body: {"memo": "이 답변의 3번째 문단이 핵심"}

응답:
{"status": "ok", "bookmark_id": "…", "memo": "이 답변의 3번째 문단이 핵심"}
```

- 메모는 앞뒤 공백을 제거한 뒤 저장하고, 빈 문자열/`null` 이면 `NULL`(메모 삭제)로 기록한다.
- 본인 소유(`user_id` 일치) 북마크가 아니면 `404 BOOKMARK NOT FOUND` 를 반환한다.

---

### 스레드 절단 (질문 수정 후 재개)
```bash
POST /threads/thread-123/truncate
Authorization: Bearer <token>
Body: {"keep_human_message_count": 2}

# 사용자 메시지 2개까지만 유지, 이후 모두 삭제
```

---

## 🚀 배포 & 환경 설정

### 필수 환경 변수
```bash
# 모델 설정
MODEL_PROVIDER=openai|ollama|google
MODEL_NAME=gpt-4o-mini
MODEL_API_KEY=sk-...
MODEL_BASE_URL=http://localhost:11434

# 데이터베이스
POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_DATABASE=postgres
POSTGRESQL_USER=postgres
POSTGRESQL_PASSWORD=...

# 캐시
REDIS_URL=redis://localhost:6379

# 인증
AUTH_TOKEN_SECRET=your-secret-key (없으면 임시 키 생성)
AUTH_TOKEN_TTL_SECOND_COUNT=604800  # 7일

# 대화 압축
CONTEXT_COMPRESSION_ENABLED=true
CONTEXT_COMPRESSION_TRIGGER_MESSAGE_COUNT=14
CONTEXT_COMPRESSION_TRIGGER_TOKEN_COUNT=3000
```

### 시작
```bash
python backend/server.py
# 기본 포트: 8000
```

---

## 📝 요약

| 단계 | 함수 | 시간 | 결과 |
|------|------|------|------|
| **1. 요청** | `stream_async()` → `AuthService` | ~10ms | 인증, 스레드 검증 |
| **2. 압축** | `_compress_context_if_needed_async()` | ~500-2000ms | 요약 생성 (필요시) |
| **3. 그래프 로드** | `_get_or_create_compiled_graph()` | ~50ms | 캐시 조회 or 신규 생성 |
| **4. 체크포인트 복원** | `compiled_graph.astream()` | ~20-100ms | 기존 메시지 로드 |
| **5. 미들웨어** | `ThinkTrimmingMiddleware` | ~5ms | 생각 토큰 제거 |
| **6. LLM 호출** | LLM API | **~1-30s** | 토큰 스트리밍 |
| **7. 클라이언트 전송** | NDJSON/평문 | ~1ms/token | 실시간 렌더링 |
| **8. 체크포인트 저장** | LangGraph 자동 | ~50-200ms | 상태 영구 기록 |

**총 소요 시간**: 모델 추론 시간이 대부분 (LLM 응답 품질에 따라 가변)

---

## 📚 관련 파일

- **엔트리포인트**: `backend/server.py`
- **API 라우터**: 
  - `backend/app/llm/api/chat_api_router.py`
  - `backend/app/orchestrator/api/orchestrator_api_router.py`
- **에이전트 팩토리**: `backend/app/llm/agent/deep_agent_factory.py`
- **대화 압축**: `backend/app/llm/compression/`
- **데이터 모델**: `backend/app/llm/repository/`
- **프론트엔드**: `frontend/src/`
