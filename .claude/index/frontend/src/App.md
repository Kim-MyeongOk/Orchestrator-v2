파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\App.jsx`

컴포넌트 기능: `App` - 최상위 화면 조립 및 전역 상태 소유 (방·북마크·스트리밍·TTS/STT·참조·프리셋)

세션 만료 대비:
- `INITIAL_LOGOUT_REASON_TEXT` : 모듈 로드 시 **한 번만** 사유를 꺼낸다.
  컴포넌트 안에서 꺼내면 StrictMode 이중 마운트의 첫 마운트가 값을 소비해 안내가 뜨지 않는다
- `isSendInFlightRef` : 전송 중에는 초안 자동 삭제를 막는다 (401 로 튕길 때 보낸 문장을 되살리기 위함)
- 전송 완료 후 초안 삭제는 `getAuthToken()` 이 남아 있을 때만 한다 —
  `location.replace()` 는 실행을 즉시 멈추지 않아 401 이어도 `await` 다음 줄이 실행되기 때문

상태(State):
- `inputValue` : 입력창 텍스트 (초기값은 저장된 초안에서 복원)
- `referencedText` : 드래그로 담은 발췌 참조 1건 (전송 후 비움)
- `selectedReferenceList` : 우클릭으로 담은 답변 참조 배열 `[{ messageId, agentIndex, previewText }]` (전송 후 비움)
- `attachedImageList` : 첨부 이미지 `[{ attachmentId, fileName, previewUrl, imageUrl, isUploading, errorText }]` (전송 후 비움)
- `presetName` : LLM 파라미터 프리셋 (LOW/MEDIUM/HIGH, 전송 후에도 유지)
- `availablePresetNames` : 서버에서 받은 프리셋 목록
- `sidebarTabName` / `scrollTargetAgentIndex` / `statusInfo` / `apiUrlText` / `modelNameList` / `isDeveloperMode`

하위 함수 기능:
- `onSend()`: 입력값을 참조·프리셋과 함께 전송하고 참조 상태를 비움
- `onRetryError()`: 실패한 턴의 `retryTurnOption` 을 그대로 다시 실어 재시도
- `onQuoteText()`: 드래그 발췌를 `referencedText` 로 담음
- `onToggleReference()`: 답변 참조 담기/빼기 (최대 `REFERENCE_MAXIMUM_COUNT`=10)
- `onRemoveReference()`: 칩의 ✕ 로 답변 참조 1건 제거
- `onClearAllReferences()`: 발췌·답변 참조 전체 해제
- `clearRoomScopedReference()`: 방이 바뀌는 길목에서 참조를 비움 (참조는 "이 방의 N번째 답변" 이라 방을 옮기면 뜻을 잃는다)
- `onSubmitEdit()`: 체크포인트 절단 후 재개, 잘려나간 답변을 가리키던 참조도 함께 정리
- `onAttachImageFileList(fileList)`: 이미지 첨부. 먼저 로컬 미리보기(`createObjectURL`)를 띄우고
  업로드 결과로 각 항목을 갱신한다 — 업로드를 기다렸다 그리면 반응이 느리게 느껴진다.
  최대 `IMAGE_ATTACHMENT_MAXIMUM_COUNT`(5)장
- `onRemoveImage(attachmentId)`: 첨부 제거 (`revokeObjectURL` 로 미리보기 메모리 해제)
- `onToggleRecording()`: 음성 받아쓰기 토글 (시작 시 TTS 정지)
- `onCreateRoom()` / `onSwitchRoom()` / `onDeleteRoom()`: 방 조작 + 마이크·참조 정리
- `onOpenBookmark()` / `onConfirmReset()` / `onToggleDeveloperMode()` / `onApiUrlChange()`
