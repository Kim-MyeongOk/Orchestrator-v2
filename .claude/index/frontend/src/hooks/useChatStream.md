파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\hooks\useChatStream.js`

Hook 기능: `useChatStream` - 스트리밍 1턴 실행. 5xx/네트워크 오류 시 지수 백오프 자동 재시도, 최종 실패 시 수동 재시도 버튼 제공

턴 옵션 (`turnOption` 객체로 전달):
- `referencedText` : 드래그 발췌
- `referencedMessageIdList` : 답변 참조 ID 배열 (`["agent-0", "agent-2"]`)
- `presetName` : LLM 파라미터 프리셋

> 전부 선택값이라 위치 인자로 늘어놓으면 호출부에서 하나만 빠뜨려도 조용히 기본값으로 나간다. 그래서 객체로 받는다.

성능:
- 토큰마다 `setState` 하면 렌더가 과해지므로 `ref` 에 누적하고 `requestAnimationFrame` 으로 한 번씩 흘려보낸다
- 재시도 상수 : `STREAM_MAXIMUM_RETRY_COUNT`=3, `STREAM_BASE_DELAY_MS`=1000 (1초 → 2초 → 4초)

하위 함수 기능:
- `executeStreamTurnAsync(room, messageText, turnOption)`: 스트리밍 1턴 실행 (재시도 루프 포함)
- `sendMessageAsync(room, messageText, turnOption)`: 사용자 메시지를 먼저 저장(참조 정보 포함)한 뒤 스트리밍 시작
- `stopStreaming()`: AbortController 로 중단 (받은 부분까지는 저장)
- `scheduleStreamFlush()` / `cancelPendingFlush()`: rAF 기반 렌더 스로틀

에러 메시지에 붙는 재시도 정보: `retryMessageText`, `retryTurnOption`
