##################################################
# Tavily 서치 도구 팩토리
# TAVILY_API_KEY 가 설정된 경우에만 웹 검색 도구를 생성한다 (미설정 시 None — 도구 없이 동작).
# uv add langchain-tavily
##################################################

import os

from typing import Optional

from langchain_core.tools import BaseTool
from langchain_tavily     import TavilySearch


class TavilySearchToolFactory:
    @staticmethod
    def create() -> Optional[BaseTool]:
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not tavily_api_key or not tavily_api_key.strip():
            return None
        maximum_result_count = int(os.getenv("TAVILY_MAX_RESULT_COUNT", "5"))
        return TavilySearch(
            tavily_api_key = tavily_api_key.strip(),
            max_results    = maximum_result_count
        )
