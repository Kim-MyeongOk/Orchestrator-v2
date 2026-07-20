##################################################
# DeepAgentFactory 유닛 테스트
# create_deep_agent 를 monkeypatch 로 대체하여 (실제 그래프 컴파일 없이)
# 체크포인터가 그대로 전달(passthrough)되는지 검증한다. DB / Redis 불필요.
#
# 실행 : .venv\Scripts\python.exe -m pytest -v
##################################################

import app.llm.agent.deep_agent_factory as deep_agent_factory_module

from app.llm.agent.deep_agent_factory  import DeepAgentFactory
from app.llm.agent.model_configuration import ModelConfiguration


def _create_test_model_configuration() -> ModelConfiguration:
    # ollama 는 api_key 불필요 + ChatOllama 생성이 네트워크 연결 없이 동작하므로 테스트에 적합하다
    return ModelConfiguration(provider = "ollama", model_name = "test-model", base_url = "http://localhost:11434")


class TestDeepAgentFactoryCheckpointerPassthrough:
    def test_checkpointer_defaults_to_none(self, monkeypatch):
        captured_kwargs_dictionary = {}

        def fake_create_deep_agent(**keyword_arguments):
            captured_kwargs_dictionary.update(keyword_arguments)
            return "fake-compiled-graph"

        monkeypatch.setattr(deep_agent_factory_module, "create_deep_agent", fake_create_deep_agent)
        compiled_graph = DeepAgentFactory.create(_create_test_model_configuration())
        assert compiled_graph                             == "fake-compiled-graph"
        assert captured_kwargs_dictionary["checkpointer"] is None

    def test_checkpointer_instance_passed_through(self, monkeypatch):
        captured_kwargs_dictionary = {}

        def fake_create_deep_agent(**keyword_arguments):
            captured_kwargs_dictionary.update(keyword_arguments)
            return "fake-compiled-graph"

        monkeypatch.setattr(deep_agent_factory_module, "create_deep_agent", fake_create_deep_agent)
        sentinel_checkpointer = object()
        DeepAgentFactory.create(_create_test_model_configuration(), checkpointer = sentinel_checkpointer)
        assert captured_kwargs_dictionary["checkpointer"] is sentinel_checkpointer

    def test_system_prompt_and_tool_list_passed_through(self, monkeypatch):
        captured_kwargs_dictionary = {}

        def fake_create_deep_agent(**keyword_arguments):
            captured_kwargs_dictionary.update(keyword_arguments)
            return "fake-compiled-graph"

        monkeypatch.setattr(deep_agent_factory_module, "create_deep_agent", fake_create_deep_agent)
        sentinel_tool_list = [lambda : None]
        DeepAgentFactory.create(_create_test_model_configuration(), system_prompt = "시스템 프롬프트", tool_list = sentinel_tool_list)
        assert captured_kwargs_dictionary["system_prompt"] == "시스템 프롬프트"
        assert captured_kwargs_dictionary["tools"]         is sentinel_tool_list
