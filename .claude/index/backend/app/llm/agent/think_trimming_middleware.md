파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\agent\think_trimming_middleware.py`

클래스 기능: `ThinkTrimmingMiddleware` - 모델 호출 직전에만 트리밍+윈도잉을 적용 (체크포인트 원본 보존)

> **`before_model` 훅을 쓰지 않는 이유** : 반환값이 체크포인트에 다시 기록된다.
> `awrap_model_call` 은 모델 요청(ModelRequest)만 override 하고 State 는 그대로 둔다.

모니터 그래프(`/stream` 경로)에 붙는다. 오케스트레이터 그래프에는 `ImageReinjectionMiddleware` 가 붙는다.

하위 함수 기능:
- `__init__(window_message_count)`: 윈도 크기 설정 (기본 20)
- `awrap_model_call(request, handler)`: `ThinkTokenHelper.prepare_model_input()` 으로 슬림화 후 위임
