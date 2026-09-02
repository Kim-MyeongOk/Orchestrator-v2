파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\api\llm_api_router.py`

클래스 기능: `LLMAPIRouter` - 비동기 Job 서비스 API 라우터 (Job 제출/조회/스트리밍/취소)

하위 함수 기능:
- `__init__()`: JobManager/JobSubscription 주입, API 경로 등록
- `get_router()`: FastAPI APIRouter 객체 반환
- `chat_async()`: 동기 채팅 엔드포인트 (POST /api/v1/chat)
- `submit_job_async()`: 비동기 Job 제출 엔드포인트 (POST /api/v1/job/submit)
- `stream_job_async()`: Job 스트리밍 엔드포인트 (GET /api/v1/job/stream, SSE)
- `get_job_async()`: 단일 Job 조회 엔드포인트 (GET /api/v1/job/{job_id})
- `cancel_job_async()`: Job 취소 엔드포인트 (POST /api/v1/job/{job_id}/cancel)
- `get_job_list_async()`: Job 목록 조회 엔드포인트 (페이지네이션)
