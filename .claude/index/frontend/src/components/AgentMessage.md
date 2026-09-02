파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\components\AgentMessage.jsx`

컴포넌트 기능: `AgentMessage` - 완료된 답변 말풍선 (생각 과정 접이식 + 마크다운 본문 + 하단 액션/메타 행)

참조 관련:
- **우클릭 = 이 답변을 통째로 참조 토글.** 본문에서 텍스트를 드래그한 우클릭은 `ReferenceableText` 가 먼저 가로채고
  `stopPropagation()` 으로 끊으므로, 여기까지 온 우클릭만 답변 전체 토글이 된다.
- 선택되면 amber 링(`ring-amber-400`) + 우상단 📌 배지를 붙인다 (칩 바까지 내려가 확인하지 않아도 되도록).
- 북마크 이동 강조(indigo 링)와 겹치면 강조 쪽을 우선한다 (강조는 2초 뒤 사라짐).
- 빈 응답은 모델에 넘길 본문이 없어 참조 대상에서 제외한다 (`isReferenceable`).

주요 props: `message`, `agentIndex`, `isBookmarked`/`onToggleBookmark`, `isHighlighted`,
`isSpeaking`/`onToggleSpeak`, `onQuoteText`, `isReferenceSelected`/`onToggleReference`

하위 컴포넌트:
- `AnswerCopyButton`: 답변 마크다운 원문 클립보드 복사 (1.5초간 체크 표시)
- `AnswerBookmarkButton`: (방, 답변 순번) 북마크 토글
- `AnswerSpeakButton`: 답변 낭독 토글 (재생 중이면 정지 아이콘)

하위 함수 기능:
- `onBubbleContextMenu()`: 우클릭 시 기본 메뉴를 막고 답변 참조를 토글
