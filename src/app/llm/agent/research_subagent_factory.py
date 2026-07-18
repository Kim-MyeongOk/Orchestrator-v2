##################################################
# 리서치 서브에이전트 팩토리
# 메인 에이전트가 task() 도구로 위임 호출하는 웹 리서치 전담 서브에이전트를 정의한다.
# 서브에이전트 실행은 LangGraph 서브그래프로 돌기 때문에 astream(subgraphs=True) 청크의
# 네임스페이스가 다단계(ns_path 가 "task:<id>|..." 형태로 쌓이는 트리 구조)로 관측된다.
##################################################

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from langchain_core.tools import BaseTool


class ResearchSubAgentFactory:
    RESEARCH_SUBAGENT_NAME          = "web-researcher"
    RESEARCH_SUBAGENT_DESCRIPTION   = "최신 정보나 사실 확인이 필요한 질문을 웹에서 검색해 조사한다. 뉴스, 시세, 통계, 문서 등 모델 지식만으로 답하기 어려운 주제는 이 서브에이전트에 위임하라."
    RESEARCH_SUBAGENT_SYSTEM_PROMPT = (
        "너는 웹 리서치 전담 에이전트다. tavily_search 도구로 검색하고, "
        "검색 결과의 핵심 내용을 출처(URL)와 함께 한국어로 간결하게 요약해 보고하라. "
        "검색 결과가 없거나 신뢰하기 어려우면 그 사실을 명시하라."
    )

    @staticmethod
    def create_subagent_list(search_tool : Optional[BaseTool]) -> Optional[List[Dict[str, Any]]]:
        # 검색 도구가 없으면 서브에이전트도 만들지 않는다 (도구 없는 리서처는 무의미)
        if search_tool is None:
            return None
        return [
            {
                "name"          : ResearchSubAgentFactory.RESEARCH_SUBAGENT_NAME,
                "description"   : ResearchSubAgentFactory.RESEARCH_SUBAGENT_DESCRIPTION,
                "system_prompt" : ResearchSubAgentFactory.RESEARCH_SUBAGENT_SYSTEM_PROMPT,
                "tools"         : [search_tool]
            }
        ]
