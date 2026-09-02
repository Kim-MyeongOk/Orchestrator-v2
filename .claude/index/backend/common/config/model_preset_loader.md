파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\common\config\model_preset_loader.py`

클래스 기능: `ModelPresetLoader` - `config/setting_model_parameter.yaml` 에서 LLM 파라미터 프리셋을 읽는 정적 헬퍼

파일이 없거나 파싱에 실패해도 예외를 던지지 않고 빈 딕셔너리를 돌려준다 — 프리셋 부재가 기동을 막지 않는다.
`PRESET_CACHE` 클래스 변수에 한 번 읽은 결과를 담아 재사용한다.

> 경로가 상대 경로(`config/setting_model_parameter.yaml`)라 프로젝트 루트에서 실행해야 찾는다.

하위 함수 기능:
- `load_presets()`: YAML 로드 (캐시 우선). 파일 없음·파싱 실패 시 경고 출력 후 `{}`
- `get_preset(preset_name)`: 이름으로 프리셋 하나 조회
- `get_available_presets()`: 프리셋 이름 목록
- `clear_cache()`: 캐시 초기화
