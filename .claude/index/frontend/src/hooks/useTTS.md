파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\hooks\useTTS.js`

Hook 기능: `useTTS` - 브라우저 내장 SpeechSynthesis 낭독 (외부 라이브러리 없음)

`speechSynthesis` 는 창 전체에 하나뿐인 싱글턴이라 동시 재생이 안 된다.
그래서 `App` 에서 한 번만 만들고 "지금 어느 말풍선이 재생 중인가"(`speakingKey`)를 한 곳에서 관리한다.

> 말풍선마다 훅을 두면 B 를 눌렀을 때 A 가 취소되는데도 A 의 버튼은 정지 아이콘으로 남아
> 정지 버튼이 두 개 보인다.
>
> 긴 텍스트를 한 번에 넘기면 **Chrome 이 15초 언저리에서 임의로 끊는 알려진 버그**가 있다.
> LLM 답변은 그보다 길어서 문장 단위로 잘라 순서대로 재생해 이를 피한다.

`speechSessionIdRef`(세대 번호)로 이전 재생의 늦은 콜백을 무효화한다 —
`cancel()` 은 취소된 utterance 의 `onend` 를 뒤늦게 발생시켜, A 를 멈추고 B 를 트는 순간
그 콜백이 B 의 재생 상태를 지워버리기 때문이다.

상수: `MAXIMUM_CHUNK_LENGTH` = 180

하위 함수 기능:
- `splitTextIntoSpeechChunkList(speechText)` (모듈 함수): 문장 끝으로 자르고 긴 문장은 길이로 재분할
- `selectKoreanVoice(voiceList)` (모듈 함수): ko-KR 정확 일치 → 그 외 한국어 → 없으면 브라우저 기본
- `startSpeaking(speechKey, speechText)` / `stopSpeaking()`: 재생 · 정지
- `toggleSpeak(speechKey, speechText)`: 같은 답변이면 정지, 다른 답변이면 전환

반환: `{ isSpeechSupported, speakingKey, toggleSpeak, stopSpeaking }`
