파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\reference\reference_context_builder.py`

클래스 기능: `ReferenceContextBuilder` - 질문에 붙는 참조를 프롬프트로 조립

상수: `MESSAGE_ID_PREFIX`="agent-", `MESSAGE_MAXIMUM_COUNT`=10,
`MESSAGE_MAXIMUM_LENGTH`=4000, `TEXT_MAXIMUM_LENGTH`=2000

> 그래프 캐시를 직접 들고 오면 순환 의존이 생기므로 **`state_snapshot_loader` 콜러블만 주입**받는다.

참조는 두 종류이며 `<referenced_context>` → `[참조 내용]` → `[질문]` 순으로 쌓인다.

하위 함수 기능:
- `parse_agent_index(referenced_message_id)`: `"agent-3"` → 3. 형식 오류는 `None`
- `collect_referenced_message_list_async(thread_id, id_list)`: 체크포인트에서 본문 조회.
  **유효하지 않은 ID(형식 오류·사라진 순번·중복)는 예외 없이 건너뛴다** —
  질문 수정으로 대화가 잘리면 프론트가 들고 있던 순번이 실제로 없어질 수 있는데,
  그때 질문 전체를 실패시키면 사용자는 이유를 알 수 없는 오류만 보게 된다.
  넣는 순서는 사용자가 고른 순서가 아니라 **대화 순서**다 (모델이 시간 흐름대로 읽도록)
- `build_context_block(list)`: `<referenced_context>` 태그로 묶기 (질문과 참조 자료의 경계를 모델이 구분하도록)
- `build_message_text(message, referenced_text, context_block)`: 최종 프롬프트 조합.
  조합 결과를 그대로 체크포인트에 저장한다 — 다음 턴에도 참조 맥락이 복원되어야 후속 질문이 이어진다
