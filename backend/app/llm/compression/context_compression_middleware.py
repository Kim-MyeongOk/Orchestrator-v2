from typing import Optional

from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages           import SystemMessage
from langgraph.config                  import get_config

from app.llm.compression.context_compression_configuration import ContextCompressionConfiguration
from app.llm.compression.conversation_summary_prompt       import ConversationSummaryPrompt
from app.llm.compression.conversation_summary_repository   import ConversationSummaryRepository


##################################################
# 대화 압축 미들웨어 (프롬프트 재구성)
#
# [중요] before_model 이 아니라 awrap_model_call 을 쓰는 이유는 ThinkTrimmingMiddleware /
# ImageReinjectionMiddleware 와 같다 : before_model 의 반환값은 체크포인트에 다시 기록되므로
# 압축 결과가 원본 대화를 덮어써 버린다. 그러면 사용자가 위로 스크롤했을 때 지난 대화가 사라진다.
# awrap_model_call 은 ModelRequest 만 갈아끼우므로 체크포인트에는 원본이 그대로 남는다.
#
# 요약문 생성/저장은 API 계층(stream_async)이 astream 호출 직전에 끝내둔다.
# 여기서는 저장된 요약을 읽어 "System Message + 최근 N 개"로 프롬프트를 다시 조립하기만 한다.
#
# thread_id 는 ModelRequest 에 없어서(Runtime 에 config 필드가 없다) langgraph.config.get_config()
# 로 실행 중인 그래프의 configurable 에서 읽는다.
##################################################
class ContextCompressionMiddleware(AgentMiddleware):
    def __init__(self,
                 conversation_summary_repository : ConversationSummaryRepository,
                 compression_configuration       : ContextCompressionConfiguration) -> None:
        super().__init__()
        self.conversation_summary_repository = conversation_summary_repository
        self.compression_configuration       = compression_configuration

    @staticmethod
    def _resolve_thread_id() -> Optional[str]:
        # 그래프 실행 컨텍스트 밖(단위 테스트 등)에서는 get_config 가 실패할 수 있다 → 압축 없이 통과
        try:
            return (get_config().get("configurable") or {}).get("thread_id")
        except Exception:
            return None

    async def awrap_model_call(self, request : ModelRequest, handler):
        if not self.compression_configuration.is_enabled:
            return await handler(request)

        thread_id = ContextCompressionMiddleware._resolve_thread_id()
        if thread_id is None:
            return await handler(request)

        summary, _summarized_message_count = await self.conversation_summary_repository.get_summary_state_async(thread_id)
        if not summary:
            return await handler(request)   # 아직 요약이 없는 짧은 대화 : 원본 그대로 보낸다

        recent_message_list = request.messages[-self.compression_configuration.recent_message_keep_count:]
        compressed_system_message = SystemMessage(content = ConversationSummaryPrompt.build_chat_system_prompt(summary))
        return await handler(request.override(messages = recent_message_list, system_message = compressed_system_message))
