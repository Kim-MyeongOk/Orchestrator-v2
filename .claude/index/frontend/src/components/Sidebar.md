파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\components\Sidebar.jsx`

컴포넌트 기능: `Sidebar` - 좌측 사이드바. 새 채팅방 · 채팅방/북마크 탭 · 세션 설정

구성 (위에서 아래로):
1. 로고와 「＋ 새 채팅방」 버튼
2. 탭 전환 (채팅방 / 북마크) → `RoomList` 또는 `BookmarkList` 렌더
3. 세션 설정 — 로그인 사용자(읽기 전용) + 로그아웃, 모델 선택, 개발자 모드 토글, 세션 초기화

> **생각 정도는 여기 없다.** 입력창 톱니바퀴(`ReasoningEffortPopover`)로 옮겼다.

개발자 모드를 켜면 백엔드 API URL · Thread ID · 「API 테스트 ↗」 링크(`/dev/api-client`)가 나타난다.

props: `userId` · `roomList` · `activeRoom` · `activeRoomId` · `isStreaming` · `sidebarTabName` ·
`bookmarkList` · `modelNameList` · `defaultModelName` · `isDeveloperMode` · `apiUrlText` +
콜백 `onSidebarTabChange` · `onCreateRoom` · `onSwitchRoom` · `onRenameRoom` · `onDeleteRoom` ·
`onBlockedRename` · `onOpenBookmark` · `onRemoveBookmark` · `onUpdateBookmarkMemo` · `onModelChange` ·
`onToggleDeveloperMode` · `onApiUrlChange` · `onResetSession` · `onLogout`
