# vLLM Orchestrator Deep Agent - 코드 인덱스

## 📚 인덱스 네비게이션

이 디렉토리는 프로젝트의 모든 Python 모듈을 카테고리별로 인덱싱한 문서를 포함합니다.
소스 코드의 디렉토리 구조를 그대로 반영하므로, 해당 경로의 `.md` 파일을 참조하면 됩니다.

### 구조 규칙
- **원본**: `backend/app/orchestrator/api/orchestrator_api_router.py`
- **인덱스**: `index/backend/app/orchestrator/api/orchestrator_api_router.md`

---

## 🏗️ 주요 모듈 맵

### 1. 엔트리포인트 & 초기화
| 파일 | 설명 |
|------|------|
| [server.md](backend/server.md) | FastAPI 애플리케이션, 라우트 등록, 인증/인프라 관리 |

---

### 2. API 라우터 (엔드포인트)
| 파일 | 설명 |
|------|------|
| [llm_api_router.md](backend/app/llm/api/llm_api_router.md) | Job 서비스 API (제출/조회/스트리밍/취소) |
| [chat_api_router.md](backend/app/llm/api/chat_api_router.md) | 대화 이력 조회 API |
| [orchestrator_api_router.md](backend/app/orchestrator/api/orchestrator_api_router.md) | 오케스트레이터 스트리밍 API |

---

### 3. 에이전트 팩토리 (그래프 생성)
| 파일 | 설명 |
|------|------|
| [deep_agent_factory.md](backend/app/llm/agent/deep_agent_factory.md) | DeepAgent 그래프 조립/컴파일 |
| [chat_model_factory.md](backend/app/llm/agent/chat_model_factory.md) | 프로바이더별 ChatModel 생성 |

---

### 4. Job 관리 (비동기 작업 시스템)
| 파일 | 설명 |
|------|------|
| [job_manager.md](backend/app/llm/job/job_manager/job_manager.md) | Job 생명주기 관리 (제출/실행/취소/재시도) |

---

### 5. 저장소 (Repository Pattern)
| 파일 | 설명 |
|------|------|
| [job_repository.md](backend/app/llm/repository/job_repository.md) | llm_job 테이블 접근 |

---

### 6. 대화 압축 (Context Compression)
| 파일 | 설명 |
|------|------|
| [conversation_summarizer.md](backend/app/llm/compression/conversation_summarizer.md) | LLM 기반 대화 요약 생성 |

---

### 7. 오케스트레이터 서비스
| 파일 | 설명 |
|------|------|
| [graph_stream_executor.md](backend/app/orchestrator/service/graph_stream_executor.md) | 그래프 스트리밍 실행 |

---

### 8. 인프라 & 보안
| 파일 | 설명 |
|------|------|
| [redis_stream_client.md](backend/common/cache/redis_stream/redis_stream_client.md) | Redis Stream 클라이언트 |
| [postgresql_pool_manager.md](backend/common/database/postgresql/postgresql_pool_manager.md) | PostgreSQL 연결 풀 관리 |
| [auth_token_helper.md](backend/common/security/auth_token_helper.md) | JWT 토큰 생성/검증 |

---

## 🔄 핵심 데이터 흐름

```
요청 수신 (API Router)
    ↓
인증 검증 (AuthTokenHelper)
    ↓
Job 생성 (JobManager.submit_job_async)
    ↓
그래프 생성/캐시 조회 (DeepAgentFactory)
    ↓
체크포인트 복원 (PostgreSQL checkpoint)
    ↓
그래프 스트리밍 실행 (GraphStreamExecutor)
    ↓
청크 누적 (RedisChunkBuffer)
    ↓
클라이언트 스트림 전송 (NDJSON/SSE)
    ↓
체크포인트 저장 (LangGraph AsyncPostgresSaver)
```

---

## 📊 주요 테이블 구조

### Job 관련
- `llm_job`: Job 메타데이터 (run_id, thread_id, user_id, status)
- `llm_job_message`: Job 메시지 히스토리
- `llm_job_event`: 시스템 이벤트 로그
- `llm_job_chunk`: 스트리밍 청크 데이터
- `llm_job_task`: 작업 메트릭

### 대화 관련
- `chat_thread`: 모니터 대화 스레드
- `chat_thread_message`: 모니터 메시지
- `chat_room`: 사용자 채팅방 메타데이터
- `chat_bookmark`: 북마크 정보

### 시스템
- `auth_user`: 인증된 사용자 계정
- `checkpoints`: LangGraph 체크포인트 (파티션됨)

---

## 🚀 빠른 참조

### API 엔드포인트 찾기
→ [llm_api_router.md](backend/app/llm/api/llm_api_router.md) 또는 [orchestrator_api_router.md](backend/app/orchestrator/api/orchestrator_api_router.md)

### Job 시스템 이해하기
→ [job_manager.md](backend/app/llm/job/job_manager/job_manager.md) → [job_repository.md](backend/app/llm/repository/job_repository.md)

### 그래프 실행 파이프라인
→ [deep_agent_factory.md](backend/app/llm/agent/deep_agent_factory.md) → [graph_stream_executor.md](backend/app/orchestrator/service/graph_stream_executor.md)

### 대화 압축 로직
→ [conversation_summarizer.md](backend/app/llm/compression/conversation_summarizer.md)

### 데이터베이스/캐시
→ [postgresql_pool_manager.md](backend/common/database/postgresql/postgresql_pool_manager.md) / [redis_stream_client.md](backend/common/cache/redis_stream/redis_stream_client.md)

---

**최종 업데이트**: 2026-07-26
**소스 코드 기준**: 83개 Python 파일 인덱싱 완료
