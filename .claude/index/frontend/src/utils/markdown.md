파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\utils\markdown.js`

모듈 기능: 마크다운 렌더링 · 미리보기 · 낭독용 평문 변환 · 클립보드

`marked` 와 `dompurify` 를 번들 의존성으로 쓴다 (기존 `chat.html` 은 CDN 로드였다).

하위 함수 기능:
- `renderMarkdownToHtml(rawText)`: 마크다운 → HTML. **DOMPurify 로 LLM 이 만든 `<script>`·`onerror` 를 걷어낸다**
- `stripMarkdownForPreview(rawText, maximumLength)`: 북마크 목록용 한 줄 요약 (기호 제거 후 90자)
- `stripMarkdownForSpeech(rawText)`: 낭독용 평문.
  원문을 그대로 넘기면 "별표 별표 굵게 별표 별표" 처럼 기호까지 읽는다.
  코드블록은 "(코드 블록 생략)" 으로 바꾸고 표는 통째로 뺀다 (구분자가 소음)
- `writeTextToClipboard(copyText)`: 클립보드 API 실패 시 임시 textarea + `execCommand` 폴백
