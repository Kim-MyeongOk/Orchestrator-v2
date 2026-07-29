##################################################
# 모델 목록 / 파라미터 프리셋 조회 서비스
#
# 프론트의 모델 드롭다운과 프리셋 드롭다운이 쓰는 읽기 전용 조회다.
##################################################

import os

from typing import Any
from typing import Dict
from typing import Optional

from fastapi import HTTPException

from app.llm.api.model_preset_response import ModelPreset
from app.llm.api.model_preset_response import ModelPresetsResponse
from app.llm.api.model_preset_response import ParameterSet
from common.config.model_preset_loader import ModelPresetLoader


class ModelCatalogService:
    OLLAMA_TIMEOUT_SECOND_COUNT = 5.0

    def __init__(self, model_catalog : Optional[Any]) -> None:
        self.model_catalog = model_catalog

    async def list_models_async(self) -> Dict[str, Any]:
        # 프론트 모델 선택 드롭다운용.
        # 카탈로그 모드 : config/models.yaml 의 모델 키 목록을 그대로 노출한다 (요청의 model 값 = 카탈로그 키)
        if self.model_catalog is not None:
            model_key_list = self.model_catalog.get_model_key_list()
            # 비전 미지원 모델에서는 프론트가 첨부 버튼을 잠근다 —
            # 보내 봐야 프롬프트에서 걷히므로(ImageStrippingMiddleware) 조용히 무시되는 편이 더 나쁘다
            return {"default_model"      : self.model_catalog.get_default_model_key(),
                    "models"             : model_key_list,
                    "vision_model_list"  : [model_key for model_key in model_key_list
                                            if self.model_catalog.create_model_configuration(model_key).vision_enabled],
                    "provider"           : "catalog"}

        # 폴백 모드 : ollama 는 설치 모델을 프록시, 그 외 프로바이더는 기본 모델만 노출한다
        default_model  = os.getenv("MODEL_NAME", "qwen3-vl:4b")
        model_provider = os.getenv("MODEL_PROVIDER", "ollama").strip().lower()
        if model_provider != "ollama":
            return {"default_model" : default_model, "models" : [default_model], "provider" : model_provider}

        import httpx
        ollama_base_url = os.getenv("MODEL_BASE_URL", "http://localhost:11434")
        try:
            async with httpx.AsyncClient(timeout = ModelCatalogService.OLLAMA_TIMEOUT_SECOND_COUNT) as http_client:
                response = await http_client.get(f"{ollama_base_url}/api/tags")
                response.raise_for_status()
                model_name_list = [model_entry["name"] for model_entry in response.json().get("models", [])]
        except Exception as exception:
            raise HTTPException(status_code = 502, detail = f"OLLAMA MODEL LIST FAILED : {exception}")
        return {"default_model" : default_model, "models" : model_name_list, "provider" : model_provider}

    async def list_model_presets_async(self) -> ModelPresetsResponse:
        # LLM 모델 파라미터 프리셋 목록 반환 (LOW / MEDIUM / HIGH)
        preset_dictionary        = ModelPresetLoader.load_presets()
        preset_object_dictionary = {}
        for preset_name, preset_parameter_dictionary in preset_dictionary.items():
            # 부분 파라미터 세트 (thinking, answer) 변환
            thinking_parameter = preset_parameter_dictionary.get("thinking")
            answer_parameter   = preset_parameter_dictionary.get("answer")
            preset_object_dictionary[preset_name] = ModelPreset(
                name                  = preset_name,
                temperature           = preset_parameter_dictionary.get("temperature", 0.5),
                top_p                 = preset_parameter_dictionary.get("top_p", 0.9),
                max_completion_tokens = preset_parameter_dictionary.get("max_completion_tokens", 512),
                timeout               = preset_parameter_dictionary.get("timeout", 120),
                max_retries           = preset_parameter_dictionary.get("max_retries", 3),
                stream_usage          = preset_parameter_dictionary.get("stream_usage", True),
                default_headers       = preset_parameter_dictionary.get("default_headers", {}),
                extra_body            = preset_parameter_dictionary.get("extra_body", {}),
                num_return_sequences  = preset_parameter_dictionary.get("num_return_sequences", 1),
                thinking              = ParameterSet(**thinking_parameter) if thinking_parameter else None,
                answer                = ParameterSet(**answer_parameter) if answer_parameter else None)
        return ModelPresetsResponse(presets = preset_object_dictionary,
                                    available_preset_names = list(preset_object_dictionary.keys()))
