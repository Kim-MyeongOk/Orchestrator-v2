import os
import json

from typing import Any
from typing import Dict
from typing import Optional

##################################################
# 환경변수 헬퍼
# 환경변수 문자열을 bool / int / JSON 객체로 파싱하는 정적 유틸리티. 미설정/빈 값은 기본값 또는 None 으로 처리한다.
##################################################
class EnvironmentVariableHelper:
    @staticmethod
    def get_boolean(environment_variable_name : str, default_value : bool) -> bool:
        environment_value = os.getenv(environment_variable_name)
        if environment_value is None:
            return default_value
        return environment_value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def get_optional_integer(environment_variable_name : str) -> Optional[int]:
        environment_value = os.getenv(environment_variable_name)
        return int(environment_value) if environment_value not in (None, "") else None

    @staticmethod
    def get_optional_dictionary(environment_variable_name : str) -> Optional[Dict[str, Any]]:
        environment_value = os.getenv(environment_variable_name)
        if environment_value in (None, ""):
            return None
        value = json.loads(environment_value)
        if not isinstance(value, dict):
            raise ValueError(f"INVALID ENVIRONMENT JSON OBJECT : {environment_variable_name}")
        return value
