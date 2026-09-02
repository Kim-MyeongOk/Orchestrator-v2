파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\frontend\src\components\ReasoningEffortPopover.jsx`

컴포넌트 기능: `ReasoningEffortPopover` - 입력창 톱니바퀴. 생각 정도(reasoning effort) 설정 팝오버

답하기 전에 얼마나 오래 생각할지 고른다. ollama 는 think 레벨, google 은 thinking_budget 으로 전달된다.
값은 **방(room)별**로 저장되고, 끄면 빈 값이 되어 모델 기본 동작을 따른다.

> 예전에는 사이드바 「파라미터 프리셋」과 입력창 「생각 정도」가 따로 있었다.
> 3단계 선택이 두 군데 있으면 어느 쪽이 듣는지 헷갈려 하나로 통합했다 (1.26.50).

`lastEffortRef` 로 직전 선택을 기억해 껐다 켜면 그 값으로 돌아온다 (끄는 순간 실제 값은 `""` 가 되므로 별도 보관이 필요).
지정했을 때만 아이콘에 점을 찍는다 — 아이콘만으로는 모델 기본인지 알 수 없다.
바깥 클릭과 ESC 로 닫히며, 리스너는 열려 있을 때만 건다.

상수: `EFFORT_OPTION_LIST` (낮음/보통/높음) · `DEFAULT_EFFORT_VALUE` = "medium"

props: `isOpen` · `onToggleOpen` · `reasoningEffort` · `onReasoningEffortChange` · `isDisabled`
