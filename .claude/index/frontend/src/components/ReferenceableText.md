파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\components\ReferenceableText.jsx`

컴포넌트 기능: `ReferenceableText` - 답변 본문에서 드래그(또는 선택 후 우클릭)한 구간을 담는 「❝ 참조하기」 팝업

동작 규칙:
- 선택이 **이 말풍선 안에 온전히** 들어 있을 때만 인정한다 (여러 말풍선에 걸친 드래그는 다른 답변이 섞인다).
- 선택이 있을 때만 우클릭을 가로채고 `stopPropagation()` 한다 → 선택 없는 우클릭은 흘려보내
  `AgentMessage` 의 "답변 통째로 참조" 토글이 받는다.
- 팝업은 `createPortal` 로 body 에 그린다 — 말풍선 조상의 `overflow`/`transform` 때문에 내부 렌더 시 잘리거나
  `fixed` 좌표 기준이 어긋난다.
- 버튼에 `onMouseDown preventDefault` — 없으면 mousedown 이 선택을 풀어 click 시점에 발췌를 잃는다.
- 바깥 클릭 · Esc · 스크롤(캡처) · 리사이즈 시 닫힌다.

상수: `REFERENCE_MAXIMUM_LENGTH`=2000 (서버 `REFERENCED_TEXT_MAXIMUM_LENGTH` 와 동일)

하위 함수 기능:
- `readSelectionText()`: 이 말풍선 안에 온전히 든 선택 텍스트만 반환
- `openPopupAt()`: 화면 밖으로 나가지 않게 좌표를 가둬 팝업 표시
- `onMouseUp()`: 드래그 종료 시 한 틱 미룬 뒤 선택을 읽어 팝업 표시
- `onContextMenu()`: 선택이 있을 때만 팝업 표시 + 전파 차단
- `onQuoteClick()`: 발췌를 담고 선택 하이라이트를 걷어냄
