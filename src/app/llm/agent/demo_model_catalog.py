##################################################
# 모델 카탈로그 사용 예제
# 실행 : python src/app/llm/agent/demo_model_catalog.py
##################################################

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

from dotenv import load_dotenv

from app.llm.agent.model_catalog import ModelCatalog

if __name__ == "__main__":
    load_dotenv()
    model_catalog = ModelCatalog.load_default()
    if model_catalog is None:
        print("MODEL CATALOG NOT FOUND : config/models.yaml")
        sys.exit(1)

    print("-" * 50)
    print(f"DEFAULT MODEL KEY : {model_catalog.get_default_model_key()}")
    print(f"MODEL KEY COUNT : {len(model_catalog.get_model_key_list())}")
    print("-" * 50)
    for model_key in model_catalog.get_model_key_list():
        model_configuration = model_catalog.create_model_configuration(model_key)
        print(f"{model_key:32s} -> provider={model_configuration.provider:8s} name={model_configuration.model_name}")
    print("-" * 50)

    default_configuration = model_catalog.create_model_configuration(model_catalog.get_default_model_key(), reasoning_effort = "high")
    print(f"DEFAULT CONFIGURATION : {default_configuration}")
