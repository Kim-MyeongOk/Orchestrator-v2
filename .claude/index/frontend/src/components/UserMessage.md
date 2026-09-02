파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\components\UserMessage.jsx`

컴포넌트 기능: `UserMessage` - 사용자 질문 말풍선 (더블클릭/✎ 로 수정 → 그 지점부터 대화 재개)

참조 되짚기 (질문과 함께 모델에 전달된 내용을 말풍선에 표시):
- `referencedAgentIndexList` : `📌 답변 #N` 배지들 (우클릭으로 담았던 답변, amber 색)
- `referencedText` : 인용 블록 (드래그로 담았던 발췌, indigo 좌측 선 · 최대 4줄)

주요 props: `text`, `referencedText`, `referencedAgentIndexList`, `userMessageIndex`,
`isStreaming`, `onSubmitEdit`, `onBlockedEdit`

하위 함수 기능:
- 수정 모드 진입/취소/저장 (응답 중에는 `onBlockedEdit` 으로 차단)
