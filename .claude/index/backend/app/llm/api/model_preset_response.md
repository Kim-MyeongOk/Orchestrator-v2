파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\api\model_preset_response.py`

모듈 기능: `GET /config/presets` 응답 스키마 3종 (pydantic BaseModel)

`ModelPresetLoader` 가 읽은 `config/setting_model_parameter.yaml` 을 API 응답 형태로 옮긴다.

하위 클래스 기능:
- `ParameterSet`: 부분 파라미터 세트. 전 필드가 Optional 이라 thinking/answer 단계별로 일부만 덮어쓸 수 있다
- `ModelPreset`: 프리셋 하나. temperature · top_p · max_completion_tokens · timeout · max_retries ·
  stream_usage · default_headers · extra_body · num_return_sequences + 선택적 `thinking` / `answer`
- `ModelPresetsResponse`: `presets`(이름 → ModelPreset) 와 `available_preset_names` 목록

> 프리셋은 「생각 정도」로 통합되어 프론트 UI 에서는 더 이상 노출되지 않는다 (1.26.50).
> 엔드포인트와 스키마는 남아 있다.
