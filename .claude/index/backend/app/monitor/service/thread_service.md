파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agentackendpp\monitor\service	hread_service.py`

클래스 기능: `ThreadService` - 대화 복원 / 절단 / 진단 (LangGraph 체크포인트 기반)

> 그래프 캐시를 직접 들고 오면 순환 의존이 생기므로 **`compiled_graph_loader` 콜러블만 주입**받는다.
> 요약 저장소는 체크포인트 풀이 열린 뒤에야 만들어져 `set_conversation_summary_repository()` 로 나중에 주입한다.

하위 함수 기능:
- `get_thread_messages_async(thread_id, authorization)`: 체크포인트를 표시용 `[{role, text, reasoning}]` 으로 변환
  (본문 없는 도구 호출 AI 메시지는 제외 — 이 규칙이 북마크 `agent_index` 와 일치해야 한다)
- `truncate_thread_async(thread_id, truncate_request, authorization)`: 특정 질문 이후를 `RemoveMessage` 로 제거.
  잘려나간 답변의 북마크를 함께 정리하고 요약도 초기화한다
  (요약이 삭제된 대화를 계속 가리키면 모델이 지운 내용을 기억한 것처럼 답한다)
- `diagnose_thread_async(thread_id, authorization)`: 체크포인트 로드 시간 · 메시지 수 · 생각 토큰 KB
