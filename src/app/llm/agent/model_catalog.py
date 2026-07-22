##################################################
# 모델 카탈로그
# config/models.yaml 의 model_info 항목을 ModelConfiguration 으로 변환한다.
# 값 안의 ${oc.env:VAR,default} 는 OmegaConf 가 로드 시 환경변수로 치환하므로 시크릿은 .env 에 남길 수 있다.
# 카탈로그 파일이 없으면 load_default() 가 None 을 반환하고 호출부는 .env 방식으로 폴백한다.
##################################################

import os

# uv add omegaconf
from omegaconf import OmegaConf

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from app.llm.agent.model_configuration import ModelConfiguration

class ModelCatalog:
    def __init__(self, default_model_key : str, model_info_dictionary : Dict[str, Dict[str, Any]]) -> None:
        # model_info_dictionary : OmegaConf 로 ${oc.env:...} 를 이미 치환한 평범한 dict
        if not model_info_dictionary:
            raise ValueError("MODEL INFO IS EMPTY : model_info")
        if default_model_key not in model_info_dictionary:
            raise ValueError(f"DEFAULT MODEL NOT FOUND : {default_model_key}")
        self.default_model_key     = default_model_key
        self.model_info_dictionary = model_info_dictionary

    def create_model_configuration(self, model_key : str, reasoning_effort : Optional[str] = None) -> ModelConfiguration:
        # 카탈로그 항목 1개 → ModelConfiguration 변환 (reasoning_effort 는 요청별 오버라이드)
        if model_key not in self.model_info_dictionary:
            raise ValueError(f"MODEL KEY NOT FOUND : {model_key}")
        model_entry       = self.model_info_dictionary[model_key] or {}
        header_dictionary = model_entry.get("default_header_dictionary")
        if isinstance(header_dictionary, dict):
            # 헤더 값은 문자열이어야 한다. 환경변수 미설정(None)이나 빈 값("")으로 온 항목은 제외한다
            header_dictionary = {header_name : str(header_value) for header_name, header_value in header_dictionary.items() if header_value is not None and str(header_value).strip() != ""}
            header_dictionary = header_dictionary or None
        return ModelConfiguration(
            provider                  = model_entry.get("provider"),
            model_name                = model_entry.get("name") or model_entry.get("model_name"),
            api_key                   = model_entry.get("api_key"),
            base_url                  = model_entry.get("base_url"),
            temperature               = float(model_entry["temperature"])          if model_entry.get("temperature")          is not None else 0.0,
            maximum_token_count       = int(model_entry["maximum_token_count"])    if model_entry.get("maximum_token_count")  is not None else None,
            timeout_second_count      = float(model_entry["timeout_second_count"]) if model_entry.get("timeout_second_count") is not None else 120.0,
            maximum_retry_count       = int(model_entry["maximum_retry_count"])    if model_entry.get("maximum_retry_count")  is not None else 2,
            default_header_dictionary = header_dictionary,
            extra_body_dictionary     = model_entry.get("extra_body") or model_entry.get("extra_body_dictionary"),
            reasoning_enabled         = model_entry.get("reasoning_enabled"),
            context_token_count       = int(model_entry["context_token_count"])    if model_entry.get("context_token_count")  is not None else None,
            reasoning_effort          = reasoning_effort
        )

    def is_model_enabled(self, model_key : str) -> bool:
        # enable : 명시적으로 false 일 때만 비활성. 필드가 없으면 활성으로 간주(하위 호환)
        model_entry = self.model_info_dictionary.get(model_key) or {}
        return model_entry.get("enable", True) is not False

    def get_model_key_list(self) -> List[str]:
        # UI 드롭다운용 : enable=false 모델은 제외한다
        return [model_key for model_key in self.model_info_dictionary.keys() if self.is_model_enabled(model_key)]

    def get_default_model_key(self) -> str:
        return self.default_model_key

    def has_model(self, model_key : str) -> bool:
        # 정의만 되어 있으면 True (enable=false 여도 직접 요청/기본값 해석은 허용)
        return model_key in self.model_info_dictionary

    @staticmethod
    def load_default() -> Optional["ModelCatalog"]:
        # MODEL_CATALOG_PATH(기본 : 프로젝트 루트의 config/models.yaml) 에서 카탈로그를 읽는다.
        # 파일이 없으면 None → 호출부는 기존 .env(MODEL_*) 방식으로 폴백한다.
        # OmegaConf 로 로드해 ${oc.env:VAR,default} 보간을 해석한 뒤 평범한 dict 로 변환한다.
        project_root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        catalog_file_path = os.getenv("MODEL_CATALOG_PATH") or os.path.join(project_root_path, "config", "models.yaml")
        if not os.path.isfile(catalog_file_path):
            return None
        catalog_config     = OmegaConf.load(catalog_file_path)
        catalog_dictionary = OmegaConf.to_container(catalog_config, resolve = True) or {}
        model_info_dictionary = catalog_dictionary.get("model_info") or {}
        default_model_key     = catalog_dictionary.get("default_model") or next(iter(model_info_dictionary), None)
        return ModelCatalog(default_model_key, model_info_dictionary)
