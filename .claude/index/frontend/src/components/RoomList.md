파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\components\RoomList.jsx`

컴포넌트 기능: `RoomList` - 사이드바 「채팅방」 탭. 방 목록 + 인라인 이름 편집 + 삭제

> 응답 중인 방은 이름 변경이 막힌다 (`onBlockedRename` 으로 안내). 응답이 다른 방에 섞이는 것을 방지한다.

이름 편집은 더블클릭 또는 ✎ 버튼으로 시작한다. Enter 확정 · Esc 취소 · blur 시 자동 확정(최대 60자).
입력창의 `onKeyDown` 은 `stopPropagation` 한다 — Enter 가 메시지 전송으로 번지지 않게 한다.
방 이름 옆에 모델명 앞부분(`:` 앞)을 작게 표시한다.

하위 함수 기능:
- `startRename(event, room)`: 편집 시작 (응답 중이면 차단)
- `commitRename(roomId)`: 편집 확정

props: `roomList` · `activeRoomId` · `isStreaming` · `onSwitchRoom` · `onRenameRoom` · `onDeleteRoom` · `onBlockedRename`
