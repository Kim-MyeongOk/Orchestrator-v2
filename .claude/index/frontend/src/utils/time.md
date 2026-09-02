파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\utils\time.js`

모듈 기능: 상대/절대 시각 포맷 + 30초 주기 갱신 훅

하위 함수 기능:
- `formatRelativeTime(completedAtMs)`: 지금 / N분 전 / N시간 전 / N일 전 / 지난 주 / N주 전 / N개월 전 / N년 전
- `formatFullTimestamp(completedAtMs)`: 개발자 모드용 절대 시각 (밀리초까지, `2026-07-25 18:53:40.000`)
- `useTimeTick()`: 상대 시간 표시를 30초마다 다시 계산하게 하는 훅

> 메시지마다 `setInterval` 을 만들면 낭비이므로 **모듈 단위 타이머 하나**를 두고
> 구독자 Set(`timeTickSubscriberSet`)에 알리는 방식으로 공유한다.
