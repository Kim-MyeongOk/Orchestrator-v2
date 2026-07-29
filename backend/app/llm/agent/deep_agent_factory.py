from typing import Optional
from typing import List
from typing import Union
from typing import Callable
from typing import Any
from typing import Dict

from langchain_core.tools      import BaseTool
from langgraph.graph.state     import CompiledStateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver
from deepagents                import create_deep_agent
from langchain.agents          import create_agent

from app.llm.agent.model_configuration import ModelConfiguration
from app.llm.agent.chat_model_factory  import ChatModelFactory

class DeepAgentFactory:
    @staticmethod
    def create(model_configuration : ModelConfiguration, system_prompt : Optional[str] = None, tool_list : Optional[List[Union[BaseTool, Callable[..., Any], Dict[str, Any]]]] = None, checkpointer : Optional[BaseCheckpointSaver] = None, subagent_list : Optional[List[Dict[str, Any]]] = None, middleware_list : Optional[List[Any]] = None) -> CompiledStateGraph:
        # checkpointer    : PostgresSaver 등 LangGraph 체크포인터 주입 시 thread_id 기반 대화 상태가 영속화된다 (None 이면 비활성)
        # subagent_list   : SubAgent 스펙 목록. 주입 시 메인 에이전트가 task() 도구로 위임하는 트리 구조가 되어
        #                   astream(subgraphs=True) 청크에 다단계 네임스페이스(ns_path)가 쌓인다
        # middleware_list : AgentMiddleware 목록 (예 : 이미지 재주입 미들웨어)
        base_chat_model = ChatModelFactory.create(model_configuration)
        if not model_configuration.tool_calling_enabled:
            # 도구 미지원 모델(예 : llama3.2-vision) : deepagents 는 write_todos·파일 도구를 항상 바인딩하므로
            # 그대로 태우면 ollama 가 400 "does not support tools" 로 턴을 통째로 실패시킨다.
            # 도구 없는 단순 그래프로 조립한다 — 체크포인터·미들웨어는 그대로 유지되므로
            # 대화 영속화와 생각 토큰 트리밍·압축은 동일하게 동작한다.
            # 서브에이전트(task 위임)는 도구 호출이 전제라 이 경로에서는 성립하지 않는다.
            return create_agent(
                model         = base_chat_model,
                tools         = [],
                system_prompt = system_prompt,
                middleware    = middleware_list or (),
                checkpointer  = checkpointer
            )
        return create_deep_agent(
            model         = base_chat_model,
            tools         = tool_list,
            system_prompt = system_prompt,
            middleware    = middleware_list or (),
            checkpointer  = checkpointer,
            subagents     = subagent_list
        )
