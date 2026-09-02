파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\agent\chat_model_factory.py`

클래스 기능: `ChatModelFactory` - 프로바이더별 채팅 모델 팩토리 (OpenAI/Ollama/Google/Anthropic 등)

하위 함수 기능:
- `create()`: 모델 설정에 따라 적절한 ChatModel 인스턴스 생성 (프로바이더별 조건 분기)
- `_create_openai_compatible_model()`: OpenAI 호환 프로토콜 모델 생성 (Ollama, LM Studio 등)

## thinking 파라미터 규칙 — 미지원 모델을 깨뜨리지 않는다

생각 강도(`reasoning_effort`)는 **요청별** 값이고, `reasoning_enabled` 는 **카탈로그**(`config/models.yaml`) 값이다.
둘이 충돌할 때의 우선순위가 프로바이더마다 다르다.

| 프로바이더 | 판정 |
|---|---|
| ollama | `reasoning_enabled=False` → **항상 `reasoning=False`** (생각 강도가 못 덮는다)<br>그 외 → 생각 강도 > `reasoning_enabled` > `None`(모델 기본) |
| google | `gemma*` 는 thinking 미지원 → `thinking_budget`/`include_thoughts` 를 `None` 으로 두어 전송 생략 |

> ⚠️ **`reasoning_enabled: false` 는 "끄고 싶다"가 아니라 "이 모델은 thinking 을 못 쓴다"는 선언이다.**
> UI 의 생각 정도가 이를 덮으면 Ollama 가 400 (`"...does not support thinking"`) 을 던져 **턴이 통째로 실패**한다.
> `think` 를 `false` 로 보내는 것은 미지원 모델도 허용하므로, 끄는 방향은 언제나 안전하다.

회귀 테스트 : `tests/test_vision_pipeline.py::TestReasoningOverrideSafety`
