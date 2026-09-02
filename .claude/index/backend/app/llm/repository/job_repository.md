파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\repository\job_repository.py`

클래스 기능: `JobRepository` - llm_job 테이블 데이터 접근 계층

하위 함수 기능:
- `insert_job_async()`: 새로운 Job 행 삽입 (pending 상태)
- `get_job_async()`: Job ID로 단일 행 조회
- `get_jobs_async()`: 사용자의 Job 목록 조회 (페이지네이션)
- `update_job_finished_async()`: Job 완료/실패 상태 및 결과 갱신
- `lock_job_for_transfer_async()`: Job 상태 전이 시 행 락
- `cancel_job_async()`: Job 상태를 cancelled로 변경
