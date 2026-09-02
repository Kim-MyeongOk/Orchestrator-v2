파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\components\BookmarkList.jsx`

컴포넌트 기능: `BookmarkList` - 사이드바 「북마크」 탭. 저장한 답변 목록과 메모 인라인 편집

항목을 누르면 원본 채팅방으로 전환하고 해당 답변으로 스크롤·강조한다.

> 메모는 모달이 아니라 **인라인 입력창**으로 편집한다 — 사이드바가 좁아 모달을 띄우면 목록 맥락이 가려진다.

메모 편집 : Enter 저장 · Shift+Enter 줄바꿈 · Esc 취소. 저장 실패 시 입력창을 열어 둔다(내용 보존).
`MEMO_MAXIMUM_LENGTH` = 1000 — 서버 상한과 맞춘 값이다.

하위 함수 기능:
- `startEditing(event, bookmark)`: 편집 시작. `stopPropagation` 으로 방 이동을 막는다
- `cancelEditing()` / `saveEditing(bookmarkId)`: 취소 · 저장 (저장 실패 시 편집 유지)
- `onMemoKeyDown(event, bookmarkId)`: 단축키 처리

props: `bookmarkList` · `roomList` · `onOpenBookmark` · `onRemoveBookmark` · `onUpdateBookmarkMemo`
