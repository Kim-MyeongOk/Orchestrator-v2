파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\api\chat_api_router.py`

클래스 기능: `ChatAPIRouter` - 채팅 이력 조회 API 라우터

하위 함수 기능:
- `__init__()`: ChatQueryService 주입
- `get_router()`: FastAPI APIRouter 객체 반환
- `list_threads_async()`: 스레드 목록 조회 (페이지네이션)
- `get_thread_messages_async()`: 특정 스레드의 메시지 조회
