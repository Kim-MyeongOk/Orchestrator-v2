파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\components\ChatMessageList.jsx`

컴포넌트 기능: `ChatMessageList` - 중앙 대화창. 메시지 배열을 순회하며 질문 순번(수정용)과 답변 순번(북마크·참조 식별용)을 계산

순번 규칙:
- `userMessageIndex` : 질문 수정 시 체크포인트 절단 위치
- `agentMessageIndex` : 북마크 식별 · 참조 ID(`agent-{N}`) · 스크롤 대상 (`data-agent-index` 속성). 에러 말풍선은 순번을 쓰지 않는다

참조 연결:
- `selectedReferenceList` 에 해당 `agentIndex` 가 있으면 `isReferenceSelected` 로 내려 말풍선에 표시
- `onToggleReference(agentIndex, text)` 로 우클릭 토글을 상위에 위임

스크롤 동작:
- 방 전환 시 항상 하단으로, 새 메시지/청크는 하단 근처일 때만 따라감 (`NEAR_BOTTOM_THRESHOLD_PIXEL`=150)
- 북마크 이동 시 대상 말풍선으로 스크롤 + 2초 강조 (서버 복원이 늦을 수 있어 최대 20회 재시도)

하위 함수 기능:
- `onFeedScroll()`: 하단 고정 여부 갱신
- `tryScrollToTarget()`: 대상 말풍선이 나타날 때까지 재시도하며 스크롤·강조
