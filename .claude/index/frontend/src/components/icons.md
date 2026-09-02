파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\components\icons.jsx`

모듈 기능: 재사용 SVG 아이콘 모음

기존 `chat.html` 에 인라인 문자열로 흩어져 있던 SVG 를 컴포넌트로 모았다.

하위 컴포넌트 기능:
- `SendIcon()` / `StopIcon()`: 전송 · 중단
- `CopyIcon()` / `CheckIcon()`: 복사 · 복사 완료
- `BookmarkIcon({ isFilled })`: 빈 상태는 외곽선, 저장 상태는 채움
- `SpeakerIcon({ isSpeaking })`: 대기는 스피커, 재생 중은 정지 사각형
- `MicrophoneIcon()` / `SoundWaveIcon()`: 마이크 · 인식 중 막대 3개 (키프레임은 `index.css`)
- `PaperclipIcon()`: 이미지 첨부
- `SunIcon()` / `MoonIcon()`: 테마 토글
- `GearIcon()`: 생각 정도 설정 톱니바퀴
