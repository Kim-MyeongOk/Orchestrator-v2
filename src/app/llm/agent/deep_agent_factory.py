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

from app.llm.agent.model_configuration import ModelConfiguration
from app.llm.agent.chat_model_factory  import ChatModelFactory

class DeepAgentFactory:
    @staticmethod
    def create(model_configuration : ModelConfiguration, system_prompt : Optional[str] = None, tool_list : Optional[List[Union[BaseTool, Callable[..., Any], Dict[str, Any]]]] = None, checkpointer : Optional[BaseCheckpointSaver] = None) -> CompiledStateGraph:
        # checkpointer : PostgresSaver 등 LangGraph 체크포인터 주입 시 thread_id 기반 대화 상태가 영속화된다 (None 이면 비활성)
        base_chat_model = ChatModelFactory.create(model_configuration)
        return create_deep_agent(
            model         = base_chat_model,
            tools         = tool_list,
            system_prompt = system_prompt,
            checkpointer  = checkpointer
        )
