##################################################
# 에이전트 도구/서브에이전트 팩토리 유닛 테스트
# - TavilySearchToolFactory : TAVILY_API_KEY 환경변수 게이팅 검증
# - ResearchSubAgentFactory : 도구 유무에 따른 서브에이전트 스펙 생성 검증
# - DeepAgentFactory        : subagent_list passthrough 검증 (monkeypatch, 네트워크 불필요)
#
# 실행 : .venv\Scripts\python.exe -m pytest -v
##################################################

import app.llm.agent.deep_agent_factory as deep_agent_factory_module

from app.llm.agent.tavily_search_tool_factory import TavilySearchToolFactory
from app.llm.agent.research_subagent_factory  import ResearchSubAgentFactory
from app.llm.agent.deep_agent_factory         import DeepAgentFactory
from app.llm.agent.model_configuration        import ModelConfiguration


class TestTavilySearchToolFactory:
    def test_missing_api_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("TAVILY_API_KEY", raising = False)
        assert TavilySearchToolFactory.create() is None

    def test_blank_api_key_returns_none(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "   ")
        assert TavilySearchToolFactory.create() is None

    def test_api_key_creates_search_tool(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-key")
        monkeypatch.setenv("TAVILY_MAX_RESULT_COUNT", "3")
        search_tool = TavilySearchToolFactory.create()
        assert search_tool             is not None
        assert search_tool.name        == "tavily_search"
        assert search_tool.max_results == 3


class TestResearchSubAgentFactory:
    def test_no_search_tool_returns_none(self):
        assert ResearchSubAgentFactory.create_subagent_list(None) is None

    def test_search_tool_creates_subagent_specification(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-key")
        search_tool   = TavilySearchToolFactory.create()
        subagent_list = ResearchSubAgentFactory.create_subagent_list(search_tool)
        assert len(subagent_list) == 1
        subagent_specification = subagent_list[0]
        assert subagent_specification["name"]  == "web-researcher"
        assert subagent_specification["tools"] == [search_tool]
        assert "description"   in subagent_specification
        assert "system_prompt" in subagent_specification


class TestDeepAgentFactorySubAgentPassthrough:
    def test_subagent_list_passed_through(self, monkeypatch):
        captured_kwargs_dictionary = {}

        def fake_create_deep_agent(**keyword_arguments):
            captured_kwargs_dictionary.update(keyword_arguments)
            return "fake-compiled-graph"

        monkeypatch.setattr(deep_agent_factory_module, "create_deep_agent", fake_create_deep_agent)
        sentinel_subagent_list = [{"name" : "web-researcher", "description" : "리서치", "system_prompt" : "검색해라"}]
        model_configuration    = ModelConfiguration(provider = "ollama", model_name = "test-model", base_url = "http://localhost:11434")
        DeepAgentFactory.create(model_configuration, subagent_list = sentinel_subagent_list)
        assert captured_kwargs_dictionary["subagents"] is sentinel_subagent_list

    def test_subagent_list_defaults_to_none(self, monkeypatch):
        captured_kwargs_dictionary = {}

        def fake_create_deep_agent(**keyword_arguments):
            captured_kwargs_dictionary.update(keyword_arguments)
            return "fake-compiled-graph"

        monkeypatch.setattr(deep_agent_factory_module, "create_deep_agent", fake_create_deep_agent)
        model_configuration = ModelConfiguration(provider = "ollama", model_name = "test-model", base_url = "http://localhost:11434")
        DeepAgentFactory.create(model_configuration)
        assert captured_kwargs_dictionary["subagents"] is None
