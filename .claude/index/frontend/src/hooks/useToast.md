파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\hooks\useToast.js`

Hook 기능: `useToast` - 토스트 알림 목록 관리

`showToast(text, toneClass)` 로 추가하면 6초(`TOAST_VISIBLE_MS`) 뒤 자동 제거된다.
기본 색은 `bg-red-600/95` 이고 성공/안내는 호출부가 색을 넘긴다.
id 는 `useRef` 시퀀스로 발급해 같은 문구가 겹쳐도 구분된다.

반환: `{ toastList, showToast, dismissToast }`
