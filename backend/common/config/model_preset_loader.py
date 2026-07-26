import os
import yaml

from typing import Any
from typing import Dict
from typing import Optional


class ModelPresetLoader:
    """설정 파일에서 LLM 모델 파라미터 프리셋을 로드하는 헬퍼"""

    PRESET_FILE_PATH = "config/setting_model_parameter.yaml"
    PRESET_CACHE     = None   # 로드한 프리셋을 캐시

    @staticmethod
    def load_presets() -> Dict[str, Any]:
        """YAML 파일에서 프리셋을 로드한다 (캐싱 지원)"""
        if ModelPresetLoader.PRESET_CACHE is not None:
            return ModelPresetLoader.PRESET_CACHE

        preset_file_path = ModelPresetLoader.PRESET_FILE_PATH
        if not os.path.exists(preset_file_path):
            print(f"WARNING : PRESET FILE NOT FOUND : {preset_file_path}", flush = True)
            return {}

        try:
            with open(preset_file_path, "r", encoding = "utf-8") as yaml_file:
                preset_dictionary = yaml.safe_load(yaml_file) or {}
            ModelPresetLoader.PRESET_CACHE = preset_dictionary
            return preset_dictionary
        except Exception as exception:
            print(f"ERROR LOADING PRESET FILE : {preset_file_path} - {exception}", flush = True)
            return {}

    @staticmethod
    def get_preset(preset_name : str) -> Optional[Dict[str, Any]]:
        """지정한 프리셋 이름으로 파라미터 딕셔너리를 가져온다"""
        presets = ModelPresetLoader.load_presets()
        return presets.get(preset_name)

    @staticmethod
    def get_available_presets() -> list[str]:
        """사용 가능한 프리셋 이름 목록을 반환한다"""
        presets = ModelPresetLoader.load_presets()
        return list(presets.keys())

    @staticmethod
    def clear_cache() -> None:
        """캐시를 초기화한다"""
        ModelPresetLoader.PRESET_CACHE = None
