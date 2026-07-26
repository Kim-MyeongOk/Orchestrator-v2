# Orchestrator Chat Frontend (Vite + React)

기존 `chat.html`(순수 HTML/JS, 1765줄)을 Vite + React 구조로 마이그레이션한 프론트엔드다.

## 실행

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

백엔드는 별도 터미널에서 띄운다.

```bash
python src/server.py   # 포트 8000
```

백엔드가 `allow_origins=["*"]` 로 CORS 를 열어두므로 프록시 없이 바로 통신한다.
API 주소를 바꾸려면 `.env` 를 만들거나(예시는 `.env.example`) 사이드바의 **개발자 모드 → 백엔드 API URL** 에서 변경한다.

## 폴더 구조

```
frontend/
├── index.html                  Vite 진입점 (FOUC 방지 테마 스크립트 포함)
├── vite.config.js
├── tailwind.config.js          darkMode:"class" — 기존 CDN(v3) 설정 유지
├── postcss.config.js
├── public/legacy/              마이그레이션 전 HTML (참조·로그인용으로 보존)
│   ├── login.html              로그인 페이지 (아직 사용 중 · /legacy/login.html)
│   ├── chat.html               구버전 채팅 (참조용)
│   ├── index.html              모니터링 대시보드 (별개 화면)
│   └── api_client.html         백엔드가 /dev/api-client 로 서빙
└── src/
    ├── main.jsx
    ├── App.jsx                 전체 상태 조립 + 화면 배치
    ├── index.css               Tailwind 지시자 + 마크다운/스크롤바/키프레임 전역 스타일
    ├── api/chatApi.js          모든 백엔드 통신 (인증 fetch · NDJSON 스트리밍 파서)
    ├── constants/storageKeys.js
    ├── hooks/
    │   ├── useRooms.js         채팅방 CRUD · 서버 동기화 · localStorage 폴백
    │   ├── useChatStream.js    스트리밍 1턴 실행 (지수 백오프 재시도 · 중단)
    │   ├── useBookmarks.js     북마크 (답변 단위 · 서버 chat_bookmark · localStorage 폴백)
    │   ├── useTheme.js
    │   └── useToast.js
    ├── utils/
    │   ├── markdown.js         marked + DOMPurify · 클립보드
    │   └── time.js             상대 시간 / 절대 시각 · 30초 공유 타이머
    └── components/
        ├── ChatHeader.jsx          상단 바 (방 제목 · Thread · 모델 · 상태 · 테마)
        ├── ChatMessageList.jsx     대화창 (자동 스크롤 · 북마크 이동 · 순번 계산)
        ├── ChatInput.jsx           입력창 (Enter 전송 · 자동 높이 · 전송/중단 토글)
        ├── BookmarkList.jsx        사이드바 북마크 탭
        ├── Sidebar.jsx             사이드바 전체 (탭 · 세션 설정 · 개발자 모드)
        ├── RoomList.jsx            채팅방 목록 + 인라인 이름 편집
        ├── UserMessage.jsx         질문 말풍선 + 수정 모드
        ├── AgentMessage.jsx        완료된 답변 (마크다운 · 복사 · 북마크 · 메타)
        ├── StreamingAgentMessage.jsx  스트리밍 중 말풍선
        ├── MetaLine.jsx            완료/라이브 메타라인
        ├── ResetConfirmModal.jsx
        ├── ToastContainer.jsx
        └── icons.jsx
```

## 상태 관리

전역 상태 라이브러리 없이 `useState` + 커스텀 훅으로 구성했다. `App.jsx` 가 소유자다.

| 상태 | 위치 | 영속화 |
|---|---|---|
| `roomList`, `activeRoomId` | `useRooms` | 서버(chat_room) + localStorage 캐시 |
| `messages` (방별) | `useRooms` 내부 room 객체 | localStorage + 체크포인트 복원 |
| `bookmarkList` | `useBookmarks` | 서버(chat_bookmark) + localStorage 캐시 |
| `streamingState` | `useChatStream` | 휘발성 (완료 시 messages 로 커밋) |
| `inputValue`, `sidebarTabName` | `App` | — |
| 테마 / 개발자 모드 / API URL | `useTheme`, `App` | localStorage |

localStorage 키는 기존 `chat.html` 과 동일해서 **기존 사용자의 방·북마크·설정이 그대로 승계**된다.

### 스트리밍 렌더링

토큰마다 `setState` 하면 렌더가 과해지므로, `useChatStream` 이 청크를 `useRef` 에 누적하고
`requestAnimationFrame` 으로 한 프레임에 한 번만 state 로 흘려보낸다.
경과 시간 카운터(0.1초 간격)는 `LiveMetaLine` 컴포넌트로 분리해 그 노드만 리렌더된다.

마크다운은 스트리밍 중에는 파싱하지 않고(원문 `whitespace-pre-wrap`), 완료 시점에
`marked` → `DOMPurify` 를 거쳐 렌더링한다. 기존 동작과 동일하다.

## CSS

기존 `chat.html` 은 Tailwind **Play CDN(v3)** 을 썼기 때문에 동일한 v3 를 PostCSS 로 설치했다.
클래스 이름을 하나도 바꾸지 않아도 외형이 그대로 재현된다.
(v4 는 `shadow-*` 스케일과 `outline-none` 의미가 달라져 외형이 미묘하게 바뀐다.)

Tailwind 유틸리티로 표현할 수 없는 것만 `src/index.css` 에 전역 CSS 로 남겼다.

- `.chat-scroll::-webkit-scrollbar*` — 의사요소라 유틸리티로 불가
- `@keyframes` + `.typing-dot` / `.bubble-enter` / `.toast-enter`
- `.md-body *` — `marked` 가 React 밖에서 만든 HTML 이라 className 을 붙일 수 없다

## 아직 옮기지 않은 것

이번 마이그레이션은 **핵심 채팅 기능** 범위다. 아래는 구버전 `public/legacy/chat.html` 에만 있다.

- 개발자 모드 하단 **디버그 패널** — Redis 트리 폴링(3초), fetch 몽키패치 요청 로그 + cURL 복사, 채팅방 정보 표 + CSV 내보내기
- 사이드바 **드래그 리사이즈 / 접기**, 디버그 패널 높이 조절
- **휠 클릭(가운데 버튼) 자동 스크롤**

개발자 모드 자체는 유지되어 API URL · Thread ID · API 테스트 링크는 그대로 쓸 수 있다.
