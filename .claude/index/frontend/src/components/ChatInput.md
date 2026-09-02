파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\components\ChatInput.jsx`

컴포넌트 기능: `ChatInput` - 하단 입력 바 (참조 칩 바 · 자동 높이 textarea · 🎙 음성 입력 · 프리셋 선택 · 전송/중단)

참조 칩 바 (입력창 위):
- `❝ 발췌 "…" ✕` : 드래그로 담은 발췌 1건 (indigo 색)
- `📌 답변 #N ✕` : 우클릭으로 담은 답변 참조 여러 건 (amber 색, `previewText` 를 title 로 표시)
- `전체 해제` : 참조가 3건 이상일 때만 노출

이미지 첨부 (MinIO):
- 📎 첨부 버튼 · **드래그앤드롭** · **클립보드 붙여넣기(Ctrl+V)** 세 경로 모두 `onAttachImageFileList` 로 모인다
- 드래그 중에는 점선 오버레이("🖼 이미지를 여기에 놓으세요")를 띄운다.
  자식 요소를 지날 때마다 leave 가 발생해 깜빡이므로 `dragDepthRef` 로 enter/leave 를 세어 0 일 때만 푼다
- 썸네일(64px) : 업로드 중에는 흐리게 + "업로드 중…", 실패하면 빨간 테두리 + "실패", 각 썸네일에 ✕ 제거 버튼
- `dataTransfer.types` 에 "Files" 가 없으면 무시한다 (텍스트 드래그와 구분)

주요 props:
- `referencedText` / `onClearReference` : 발췌 참조
- `selectedReferenceList` / `onRemoveReference` / `onClearAllReferences` : 답변 다중 참조
- `presetName` / `onPresetNameChange` / `availablePresetNames` : 프리셋 드롭다운
- `isRecognitionSupported` / `isRecording` / `onToggleRecording` : 음성 입력 (미지원 브라우저면 버튼 숨김)
- `attachedImageList` / `isUploadingImage` / `onAttachImageFileList` / `onRemoveImage` : 이미지 첨부

하위 함수 기능:
- `onKeyDown()`: Enter 전송 / Shift+Enter 줄바꿈 / 빈 입력에서 Backspace 로 참조를 마지막부터 하나씩 해제
- 자동 높이 `useEffect`: 값이 바뀔 때마다 `scrollHeight` 로 재계산 (최대 160px)
- 포커스 `useEffect`: 참조를 담거나 스트리밍이 끝나면 입력창으로 포커스 복귀
