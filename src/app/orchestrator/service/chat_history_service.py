##################################################
# 대화 이력 조회 서비스
# thread_id 만으로 llm 도메인 리포지토리를 재사용하여 이전 대화를
# LangGraph 입력용 BaseMessage 목록으로 복원한다 (대화 재개 / Resume).
# 소유권은 llm 도메인 기준(스레드 최초 job 의 user_id)으로 강제한다.
##################################################

import uuid

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

from app.llm.repository.job_message_repository import JobMessageRepository
from app.llm.repository.job_repository         import JobRepository


class ChatHistoryService:
    def __init__(self, job_repository : JobRepository, job_message_repository : JobMessageRepository):
        self.job_repository         = job_repository
        self.job_message_repository = job_message_repository

    @staticmethod
    def _create_multimodal_content_list(content : Any, files_metadata_list : List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # files_metadata 가 있으면 멀티모달 메시지 형태로 복원한다.
        # 예 : [{"type": "text", "text": ...}, {"type": "image_url", "image_url": {...}}]
        content_list = [{"type" : "text", "text" : str(content)}]
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
    def _create_base_message(message_dictionary : Dict[str, Any]) -> Optional[BaseMessage]:
        # content 는 JSONB 라 str 또는 멀티모달 list 둘 다 올 수 있다
        role                : str = str(message_dictionary.get("role") or "")
        message_id          : str = str(message_dictionary.get("message_id") or "")
        message_content     : Any = message_dictionary.get("content")
        files_metadata_list       = message_dictionary.get("files_metadata")
        if files_metadata_list:
            message_content = ChatHistoryService._create_multimodal_content_list(message_content, files_metadata_list)

        if role == "human":
            return HumanMessage(content = message_content, id = message_id)
        if role == "ai":
            return AIMessage(content = message_content, id = message_id)
        if role == "system":
            return SystemMessage(content = message_content, id = message_id)
        if role == "tool":
            return ToolMessage(content = message_content, tool_call_id = str(message_dictionary.get("tool_call_id") or message_id))
        return None

    async def _get_fallback_message_list_async(self, thread_id : uuid.UUID, user_id : uuid.UUID) -> List[BaseMessage]:
        # llm_job_message 가 비어 있는 예외 상황에서는 llm 도메인 방식대로
        # llm_job.request_payload(사용자 입력) + 마지막 루트 ai 메시지로 맥락을 복원한다.
        job_dictionary_list = await self.job_repository.get_thread_job_list_async(thread_id, user_id)

        fallback_message_list : List[BaseMessage] = []
        for job_dictionary in job_dictionary_list:
            request_payload_dictionary = job_dictionary.get("request_payload") or {}
            for input_message_dictionary in request_payload_dictionary.get("messages") or []:
                fallback_message_list.append(HumanMessage(content = str(input_message_dictionary.get("content") or "")))
            last_ai_message_dictionary = await self.job_message_repository.get_last_root_ai_message_async(uuid.UUID(job_dictionary["run_id"]))
            if last_ai_message_dictionary is not None:
                fallback_message_list.append(AIMessage(content = last_ai_message_dictionary.get("content") or ""))
        return fallback_message_list

    async def get_chat_history_async(self, thread_id : uuid.UUID, user_id : uuid.UUID) -> List[BaseMessage]:
        # 소유권 확인 : 남의 스레드는 빈 이력으로 취급한다 (정보 노출 방지, 쓰기 경로는 JobOwnershipError 로 차단)
        owner_user_id = await self.job_repository.get_thread_owner_user_id_async(thread_id)
        if owner_user_id is not None and owner_user_id != str(user_id):
            return []

        # 루트 에이전트 메시지만 복원한다 (서브에이전트 내부 메시지는 컨텍스트에서 제외)
        message_dictionary_list = await self.job_message_repository.get_thread_root_message_list_async(thread_id)
        if not message_dictionary_list:
            return await self._get_fallback_message_list_async(thread_id, user_id)

        base_message_list : List[BaseMessage] = []
        for message_dictionary in message_dictionary_list:
            base_message = ChatHistoryService._create_base_message(message_dictionary)
            if base_message is not None:
                base_message_list.append(base_message)
        return base_message_list
