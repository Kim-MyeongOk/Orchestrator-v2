파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\index.html`

모듈 기능: React 앱 진입 HTML. 번들 로드 전에 실행되어야 하는 것만 인라인으로 남긴다

포함 항목:
- **파비콘** : 🚀 이모지를 SVG data URI 로 인라인. 선언이 없으면 브라우저가 기본 지구본을 탭에 띄운다
  (로그인 페이지 `public/legacy/login.html` 도 같은 로켓을 써서 화면을 넘어가도 탭 아이콘이 바뀌지 않는다)
- **FOUC 방지 스크립트** : React 마운트 전에 저장된 테마(없으면 시스템 테마)를 `<html>` 에 주입 — 흰 화면 깜빡임 방지
- **크리티컬 배경 CSS** : 번들 CSS 로드 전에도 올바른 배경색을 보장
- `#root` 마운트 지점 + `/src/main.jsx` 모듈 스크립트
