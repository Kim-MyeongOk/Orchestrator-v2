파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\job\job_manager\job_manager.py`

클래스 기능: `JobManager` - 비동기 Job 생명주기 관리 (제출/실행/구독/취소/재시작)

하위 함수 기능:
- `__init__()`: 리포지토리/실행기/이벤트 구독 주입
- `submit_job_async()`: 새로운 Job 생성 및 제출 (pending 상태로 시작)
- `get_job_async()`: Job ID로 단일 Job 조회
- `get_job_list_async()`: 사용자의 Job 목록 조회 (페이지네이션)
- `cancel_job_async()`: 실행 중인 Job 취소 (cancelled 상태로 전환)
- `retry_job_async()`: 실패한 Job 재시도 (새 Job으로 생성)
- `shutdown_async()`: 모든 실행 중인 Task/Stream 종료
