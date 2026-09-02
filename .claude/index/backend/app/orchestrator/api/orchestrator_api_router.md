파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\orchestrator\api\orchestrator_api_router.py`

클래스 기능: `OrchestratorAPIRouter` - 오케스트레이터 스트리밍 API 라우터

하위 함수 기능:
- `__init__()`: 그래프/서비스 컴포넌트 주입
- `stream_orchestrator_async()`: POST /api/v1/orchestrator/stream 엔드포인트 (SSE 스트리밍)
- `_create_sse_stream_async()`: SSE 이벤트 스트림 생성
- `_get_checkpoint_count_async()`: 체크포인트 행 수 조회 (디버그)
