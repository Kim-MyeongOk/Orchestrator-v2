파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agentackendpp\monitor\service\debug_service.py`

클래스 기능: `DebugService` - 개발자 모드 패널용 조회 (Redis 스냅샷 / API 테스트 페이지)

상수: `MATCHED_KEY_MAXIMUM_COUNT`=50, `LIST_TAIL_ITEM_COUNT`=30, `SCAN_COUNT_HINT`=200

하위 함수 기능:
- `_to_text(raw_value)`: Redis 응답 정규화 (decode_responses 설정과 무관하게 항상 str)
- `_try_parse_json(raw_value)`: JSON 이면 파싱, 아니면 원문 유지
- `get_api_client_page_async()`: `/dev/api-client` HTML 서빙 (백엔드가 직접 서빙 → CORS 불필요)
- `get_redis_snapshot_async(thread_id, authorization)`: `*{thread_id}*` 키 스냅샷
  (list/hash/string 타입별 표시, 실패 시 502)
