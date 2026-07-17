##################################################
# 대화 이력 조회 서비스
# thread_id 만으로 orch_message / orch_run 을 조회하여 이전 대화를
# LangGraph 입력용 BaseMessage 목록으로 복원한다 (대화 재개 / Resume).
##################################################

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

# uv add langchain-core
from langchain_core.messages import AIMessage
from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage
from sqlalchemy              import select
from sqlalchemy.ext.asyncio  import async_sessionmaker

from app.orchestrator.model.orch_message import OrchMessage
from app.orchestrator.model.orch_run     import OrchRun


class ChatHistoryService:
    def __init__(self, async_session_factory : async_sessionmaker):
        self.async_session_factory = async_session_factory

    @staticmethod
    def _create_multimodal_content_list(content : str, files_metadata_list : List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # files_metadata 가 있으면 멀티모달 메시지 형태로 복원한다.
        # 예 : [{"type": "text", "text": ...}, {"type": "image_url", "image_url": {...}}]
        content_list = [{"type" : "text", "text" : content}]
        for file_metadata_dictionary in files_metadata_list:
            file_type = str(file_metadata_dictionary.get("file_type") or "")
            file_url  = str(file_metadata_dictionary.get("file_url") or "")
            file_name = str(file_metadata_dictionary.get("file_name") or "")
            if file_type == "image":
                content_list.append({"type" : "image_url", "image_url" : {"url" : file_url}})
            else:
                # 문서(PDF 등)는 provider 별 입력 포맷이 다르므로 참조 텍스트로 복원한다.
                # (확장 지점 : provider 별 document / file 콘텐츠 블록으로 교체)
                content_list.append({"type" : "text", "text" : f"[ATTACHED FILE] {file_name} : {file_url}"})
        return content_list

    @staticmethod
    def _create_base_message(message_row : OrchMessage) -> Optional[BaseMessage]:
        message_content : Any = message_row.content
        if message_row.files_metadata:
            message_content = ChatHistoryService._create_multimodal_content_list(message_row.content, message_row.files_metadata)

        if message_row.role == "human":
            return HumanMessage(content = message_content, id = message_row.message_id)
        if message_row.role == "ai":
            return AIMessage(content = message_content, id = message_row.message_id)
        if message_row.role == "system":
            return SystemMessage(content = message_content, id = message_row.message_id)
        if message_row.role == "tool":
            return ToolMessage(content = message_content, tool_call_id = message_row.message_id)
        return None

    async def _get_fallback_message_list_async(self, thread_id : str) -> List[BaseMessage]:
        # orch_message 가 비어 있는 예외 상황(과거 flush 유실 등)에서는
        # orch_run 의 initial_input / final_output 으로 최소한의 맥락을 복원한다.
        async with self.async_session_factory() as async_session:
            select_statement = select(OrchRun).where(OrchRun.thread_id == thread_id).order_by(OrchRun.created_at.asc())
            run_row_list     = (await async_session.execute(select_statement)).scalars().all()

        fallback_message_list : List[BaseMessage] = []
        for run_row in run_row_list:
            initial_input_dictionary = run_row.initial_input or {}
            for input_message_dictionary in initial_input_dictionary.get("messages") or []:
                fallback_message_list.append(HumanMessage(content = str(input_message_dictionary.get("content") or "")))
            final_output_dictionary = run_row.final_output or {}
            output_message_list     = final_output_dictionary.get("messages") or []
            if output_message_list:
                fallback_message_list.append(AIMessage(content = str(output_message_list[-1].get("content") or "")))
        return fallback_message_list

    async def get_chat_history_async(self, thread_id : str) -> List[BaseMessage]:
        async with self.async_session_factory() as async_session:
            select_statement = select(OrchMessage).where(OrchMessage.thread_id == thread_id).order_by(OrchMessage.created_at.asc(), OrchMessage.message_order.asc())
            message_row_list = (await async_session.execute(select_statement)).scalars().all()

        if not message_row_list:
            return await self._get_fallback_message_list_async(thread_id)

        base_message_list : List[BaseMessage] = []
        for message_row in message_row_list:
            base_message = ChatHistoryService._create_base_message(message_row)
            if base_message is not None:
                base_message_list.append(base_message)
        return base_message_list
