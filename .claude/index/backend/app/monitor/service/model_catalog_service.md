파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agentackendpp\monitor\service\model_catalog_service.py`

클래스 기능: `ModelCatalogService` - 모델 목록 / 파라미터 프리셋 조회 (읽기 전용)

하위 함수 기능:
- `list_models_async()`: 카탈로그 모드면 `config/models.yaml` 의 키 목록,
  폴백 모드면 ollama 설치 모델 프록시(그 외 프로바이더는 기본 모델만). ollama 조회 실패는 502
- `list_model_presets_async()`: `ModelPresetLoader` 로 LOW/MEDIUM/HIGH 프리셋을 `ModelPresetsResponse` 로 변환
