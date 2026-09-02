파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\agent\image_stripping_middleware.py`

클래스 기능: `ImageStrippingMiddleware` - 모델 호출 직전에만 이미지 블록을 걷어낸다 (체크포인트 원본 보존)

비전 미지원 모델에 이미지가 섞인 메시지를 보내면 400 으로 턴이 통째로 실패한다.
한 번 이미지를 붙인 스레드는 그 블록이 체크포인트에 남아 매 턴 다시 실려 나가므로,
모델을 비전 미지원으로 바꾸는 순간부터 그 방은 영영 대화가 안 된다.

> 원칙은 `ThinkTrimmingMiddleware` 와 같다 — `awrap_model_call` 로 프롬프트만 갈아끼우고 State 는 그대로 둔다.
> 그래야 비전 모델로 되돌렸을 때 이미지가 살아 있고 화면의 지난 대화도 깨지지 않는다.

`server.py` 의 `_create_monitor_compiled_graph()` 가 카탈로그 선언을 보고 붙인다.
- `vision_enabled = false` → `ImageStrippingMiddleware()` : 전부 제거
- `image_maximum_count = N` → `ImageStrippingMiddleware(N)` : 최신 N장만 유지

하위 함수 기능:
- `__init__(image_maximum_count)`: None 이면 전부 제거, N 이면 최신 N장만 남긴다
- `awrap_model_call(request, handler)`: `ImageContentHelper` 로 걷어낸 메시지로 `request.override()` 후 위임
