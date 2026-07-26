from typing import Any
from typing import List
from typing import Optional

from langchain_core.messages import AIMessage
from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage

from app.llm.compression.compression_result                import CompressionResult
from app.llm.compression.context_compression_configuration import ContextCompressionConfiguration
from app.llm.compression.conversation_summary_prompt       import ConversationSummaryPrompt
from app.llm.compression.conversation_summary_repository   import ConversationSummaryRepository
from app.llm.compression.token_count_helper                import TokenCountHelper


##################################################
# 대화 요약 생성기
#
# 임계치를 넘은 스레드의 오래된 대화를 LLM 으로 요약해 chat_room 에 저장하고,
# 이번 턴에 절약된 토큰 수를 계산한다.
#
# 요약 자체도 LLM 호출이라 비용이 든다. 그래서 "아직 요약에 반영되지 않은 오래된 대화"가
# 실제로 쌓였을 때만 호출하고, 그렇지 않으면 기존 요약을 그대로 재사용한다.
##################################################
class ConversationSummarizer:
    def __init__(self,
                 conversation_summary_repository : ConversationSummaryRepository,
                 compression_configuration       : ContextCompressionConfiguration) -> None:
        self.conversation_summary_repository = conversation_summary_repository
        self.compression_configuration       = compression_configuration

    @staticmethod
    def _format_message_for_summary(message : BaseMessage) -> str:
        # 요약 입력용 한 줄 표기. 도구 호출처럼 본문이 없는 메시지는 빈 문자열로 걸러진다.
        body_text = TokenCountHelper._extract_plain_text(message).strip()
        if not body_text:
            return ""
        if isinstance(message, HumanMessage):
            return f"사용자 : {body_text}"
        if isinstance(message, AIMessage):
            return f"AI : {body_text}"
        return ""

    def _is_compression_needed(self, message_list : List[BaseMessage], total_token_count : int) -> bool:
        if not self.compression_configuration.is_enabled:
            return False
        if len(message_list) > self.compression_configuration.trigger_message_count:
            return True
        return total_token_count > self.compression_configuration.trigger_token_count

    async def _generate_summary_async(self, chat_model : Any, previous_summary : Optional[str], older_message_list : List[BaseMessage]) -> Optional[str]:
        conversation_text_list = [text for text in (ConversationSummarizer._format_message_for_summary(message) for message in older_message_list) if text]
        if not conversation_text_list:
            return previous_summary
        summarization_message_list = [
            SystemMessage(content = ConversationSummaryPrompt.build_system_prompt(self.compression_configuration.summary_line_count)),
            HumanMessage(content = ConversationSummaryPrompt.build_summarization_request(previous_summary, conversation_text_list))
        ]
        # 요약 실패가 본 대화를 막으면 안 된다 — 실패하면 기존 요약을 유지한 채 그대로 진행한다
        try:
            summary_message = await chat_model.ainvoke(summarization_message_list)
        except Exception as exception:
            print(f"CONVERSATION SUMMARY FAILED : {exception}", flush = True)
            return previous_summary
        summary_text = TokenCountHelper._extract_plain_text(summary_message).strip()
        return summary_text or previous_summary

    async def compress_if_needed_async(self, thread_id : str, message_list : List[BaseMessage], chat_model : Any) -> CompressionResult:
        # 압축 전 전체 히스토리 토큰 수 (절약량의 기준선)
        total_token_count = TokenCountHelper.count_message_list_token(message_list, chat_model)
        if not self._is_compression_needed(message_list, total_token_count):
            return CompressionResult.create_uncompressed()

        previous_summary, summarized_message_count = await self.conversation_summary_repository.get_summary_state_async(thread_id)

        recent_keep_count  = self.compression_configuration.recent_message_keep_count
        older_boundary     = max(0, len(message_list) - recent_keep_count)
        # 아직 요약에 반영되지 않은 구간만 새로 요약한다 (이미 반영된 앞부분은 previous_summary 가 대신한다)
        new_older_message_list = message_list[summarized_message_count : older_boundary]

        summary = previous_summary
        if new_older_message_list:
            summary = await self._generate_summary_async(chat_model, previous_summary, new_older_message_list)
            if summary and summary != previous_summary:
                await self.conversation_summary_repository.update_summary_async(thread_id, summary, older_boundary)

        if not summary:
            return CompressionResult.create_uncompressed()

        # 실제 전송될 프롬프트 = 요약을 담은 System Message + 최근 N 개 원본
        recent_message_list = message_list[older_boundary:]
        sent_message_list   = [SystemMessage(content = ConversationSummaryPrompt.build_chat_system_prompt(summary))] + recent_message_list
        sent_token_count    = TokenCountHelper.count_message_list_token(sent_message_list, chat_model)

        saved_token_count = max(0, total_token_count - sent_token_count)
        print(f"CONTEXT COMPRESSED : THREAD {thread_id} - BEFORE {total_token_count} - AFTER {sent_token_count} - SAVED {saved_token_count}", flush = True)
        return CompressionResult(is_compressed = True, saved_token_count = saved_token_count, summary = summary)
