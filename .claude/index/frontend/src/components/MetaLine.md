파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\components\MetaLine.jsx`

모듈 기능: 답변 하단 메타라인 두 종류 (완료본 / 스트리밍 중)

토큰 메타는 `⏱ {경과}s · 생각 {N} 토큰 · 응답 {N} 토큰` 형식이다.

하위 컴포넌트 기능:
- `CompletedMetaLine({ meta, isDeveloperMode })`: 완료된 답변용.
  개발자 모드는 절대 시각(ms)+토큰 메타, 일반 모드는 상대 시간(30초 주기 자동 갱신).
  `completed_at` 이 없는 레거시 데이터는 토큰 메타만 고정 표시한다
- `LiveMetaLine({ startedAt, reasoningTokenCount, answerTokenCount })`: 스트리밍 중 0.1초 간격 경과 카운터.
  이 컴포넌트만 리렌더되도록 분리해 말풍선 본문은 토큰 도착 시에만 다시 그린다
