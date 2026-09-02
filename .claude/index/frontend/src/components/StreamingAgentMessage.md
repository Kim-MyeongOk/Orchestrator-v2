파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\components\StreamingAgentMessage.jsx`

컴포넌트 기능: `StreamingAgentMessage` - 스트리밍 중인 답변 말풍선

> 완료본(`AgentMessage`)과 달리 **마크다운을 렌더링하지 않고** 원문을 `whitespace-pre-wrap` 으로 흘려보낸다.
> 파싱 중인 마크다운이 깜빡이는 것을 막고 토큰당 파싱 비용도 아낀다.

생각 과정(`<details>`)은 첫 조각에서 자동으로 펼치고 답변 본문이 시작되면 접는다.
사용자가 직접 접었다 편 것을 스트리밍 리렌더가 되돌리지 않도록 열림 상태를 state 로 들고 있는다.
첫 토큰 전에는 타이핑 인디케이터(점 3개)를 보여준다.

props: `streamingState` (`{ text, reasoning, reasoningTokenCount, answerTokenCount, startedAt, retryNoticeText }`)
