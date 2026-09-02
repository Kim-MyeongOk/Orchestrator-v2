파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\hooks\useSTT.js`

Hook 기능: `useSTT` - 브라우저 내장 SpeechRecognition 받아쓰기 (외부 라이브러리 없음)

마이크는 창 전체에 하나뿐이라 `App` 에서 한 번만 만들어 쓴다 (여러 곳에 두면 두 세션이 같은 마이크를 다툰다).

> 결과를 입력창에 그대로 덮어쓰지 않고 **세 조각을 합쳐** 만든다.
> `baseText`(녹음 시작 시점 입력창) + `finalTranscript`(확정분) + `interim`(말하는 중)
>
> 중간 결과는 다음 이벤트에서 더 정확한 문장으로 통째로 대체되므로,
> 이어 붙이기만 하면 "안녕 안녕하세 안녕하세요" 처럼 중간 단계가 전부 쌓인다.

`continuous = true` 로 두어 버튼을 다시 누를 때까지 듣는다.
Chrome 은 침묵이 이어지면 스스로 세션을 끝내므로 `onend` 에서 자동 재시작한다
(`isStoppingRef` 로 사용자가 멈춘 경우와 구분).
콜백은 `ref` 로 들고 있는다 — 이벤트 핸들러는 시작할 때 한 번만 붙어서 옛 참조를 계속 잡기 때문이다.

상수: `RECOGNITION_LANGUAGE` = "ko-KR" · `ERROR_MESSAGE_BY_CODE` (not-allowed · service-not-allowed · audio-capture · network)

하위 함수 기능:
- `startRecording(baseText)`: 인식 시작. 이미 적은 글 뒤에 한 칸 띄우고 이어 붙인다
- `stopRecording()`: `abort()` 가 아니라 `stop()` — 확정 전 마지막 말을 버리지 않는다
- `toggleRecording(baseText)`: 시작/정지 토글

반환: `{ isRecognitionSupported, isRecording, toggleRecording, stopRecording }`
