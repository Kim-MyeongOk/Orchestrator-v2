파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\hooks\useBookmarks.js`

Hook 기능: `useBookmarks` - 북마크 목록. 서버(`chat_bookmark`)가 원본, localStorage 는 오프라인 폴백 캐시

식별 키는 **(방, 방 안에서의 에이전트 답변 순번)** 조합이다.
`thread_id` 는 대화 전체를 가리키는 값이라 답변 하나를 지목할 수 없어 쓰지 않는다.

> **토글은 낙관적으로 처리한다** — 화면을 먼저 바꾸고 서버 호출은 흘려보낸다(실패해도 되돌리지 않는다).
> 왕복 지연만큼 늦게 반영되면 하트가 뒤늦게 깜빡이는 것처럼 보이기 때문이다.
>
> **메모 수정은 반대다** — 실패하면 되돌리고 토스트로 알린다.
> 사용자가 직접 입력한 내용이라 조용히 사라지면 저장된 줄로 오해한다.

최초 로드 시 캐시에만 있고 서버에 없는 항목은 등록을 재시도한다 (구버전 데이터 이관 + 지난 실패분 복구).

하위 함수 기능:
- `readCachedBookmarkList(currentUserId)` (모듈 함수): 구/신 캐시 포맷을 모두 읽는다
- `isBookmarked(roomId, agentIndex)`: 저장 여부
- `toggleBookmark(roomId, agentIndex, answerText, completedAtMs)`: 추가/삭제 (미리보기 500자 스냅샷 저장)
- `updateBookmarkMemo(bookmarkId, memoText)`: 메모 저장. 서버가 자른 결과로 맞춘다. 성공 여부를 반환
- `removeRoomBookmarks(roomId)`: 방 삭제 시 정리
- `removeBookmarksFromAgentIndex(roomId, fromAgentIndex)`: 질문 수정으로 대화가 절단됐을 때 잘려나간 답변의 북마크 제거
