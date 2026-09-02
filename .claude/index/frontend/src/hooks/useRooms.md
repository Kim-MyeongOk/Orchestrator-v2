파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\hooks\useRooms.js`

Hook 기능: `useRooms` - 채팅방 상태. 서버(`chat_room`)가 원본, localStorage 는 오프라인 폴백 캐시

room = `{ roomId, threadId, title, model, reasoningEffort, lastRunId?, messages }`

> `messages === null` 은 "아직 서버에서 안 불러온 방"(lazy 로드 대상)이고, `[]` 는 빈 대화다.
> 활성 방의 messages 가 null 이면 체크포인트에서 자동 복원한다 (`restoringThreadIdRef` 로 중복 요청 방지).

최초 로드는 서버 우선이고, 서버가 비었는데 로컬 캐시가 있으면 최초 1회 마이그레이션으로 서버에 등록한다.
방이 하나도 없으면 빈 방을 자동 생성한다.

하위 함수 기능:
- `createEmptyRoom()` (모듈 함수): UUID 로 roomId·threadId 를 발급한 빈 방
- `updateRoom(roomId, updateRoomCallable)`: 방 단위 부분 갱신 헬퍼
- `restoreRoomMessagesAsync(room)`: 체크포인트에서 대화 복원 (실패 시 빈 대화로 시작)
- `createRoom()` / `switchRoom(roomId)` / `renameRoom(roomId, title)` / `deleteRoom(roomId)`: CRUD.
  마지막 방을 지우면 빈 방을 새로 만든다
- `resetActiveSession()`: 새 Thread 발급 + 대화 초기화 (체크포인트와 분리)
- `setRoomModel(roomId, modelName)` / `setRoomReasoningEffort(roomId, reasoningEffort)`: 방별 설정
- `appendMessage` / `replaceMessages` / `removeErrorMessage`: 메시지 조작
- `applyFirstMessageTitle(roomId, messageText)`: 첫 질문 앞 24자를 방 제목으로
- `setRoomLastRunId(roomId, runId)`: 디버그 패널용 run_id 기록
- `dropInvalidRoomModels(validModelNameSet)`: 프로바이더 변경으로 무효가 된 모델을 기본으로 되돌린다
