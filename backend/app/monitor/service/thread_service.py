##################################################
# 스레드 서비스 (대화 복원 / 절단 / 진단)
#
# 대화 원본은 LangGraph 체크포인트(messages 채널)에 있다. 이 서비스는 그것을
# 표시용으로 바꾸거나(복원), 특정 질문 이후를 잘라내거나(절단), 로드 비용을 재는(진단) 일을 한다.
##################################################

import time

from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional

from fastapi import HTTPException

from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import RemoveMessage

from app.database.table_query.chat_bookmark_query import ChatBookmarkQuery
from app.llm.agent.think_token_helper           import ThinkTokenHelper
from app.monitor.api.truncate_thread_request    import TruncateThreadRequest
from app.monitor.service.auth_service           import AuthService


class ThreadService:
    AGENT_MESSAGE_TYPE_NAME_TUPLE = ("AIMessage", "AIMessageChunk")

    def __init__(self,
                 checkpoint_connection_pool     : Any,
                 auth_service                   : AuthService,
                 compiled_graph_loader          : Callable,
                 conversation_summary_repository : Any = None) -> None:
        # compiled_graph_loader() -> CompiledGraph : 그래프 캐시를 직접 들고 오면 순환 의존이 생겨 호출 방법만 받는다
        self.checkpoint_connection_pool      = checkpoint_connection_pool
        self.auth_service                    = auth_service
        self.compiled_graph_loader           = compiled_graph_loader
        self.conversation_summary_repository = conversation_summary_repository

    def set_conversation_summary_repository(self, conversation_summary_repository : Any) -> None:
        # 요약 저장소는 체크포인트 풀이 열린 뒤에야 만들어지므로 나중에 주입한다
        self.conversation_summary_repository = conversation_summary_repository

    async def _load_message_list_async(self, thread_id : str) -> List[BaseMessage]:
        state_snapshot = await self.compiled_graph_loader().aget_state({"configurable" : {"thread_id" : thread_id}})
        return state_snapshot.values.get("messages", []) if state_snapshot else []

    async def get_thread_messages_async(self, thread_id : str, authorization : Optional[str]) -> Dict[str, Any]:
        # 대화 내용 복원 : 체크포인트(messages 채널)를 표시용 [{role, text, reasoning}] 으로 변환한다
        user_id = self.auth_service.require_authenticated_user_id(authorization)
        await self.auth_service.assert_thread_accessible_async(user_id, thread_id)

        display_message_list = []
        for message in await self._load_message_list_async(thread_id):
            message_type              = type(message).__name__
            body_text, reasoning_text = ThinkTokenHelper.extract_message_texts(message)
            if message_type == "HumanMessage" and body_text:
                display_message_list.append({"role" : "user", "text" : body_text})
            elif message_type in ThreadService.AGENT_MESSAGE_TYPE_NAME_TUPLE and body_text:
                # 도구 호출 전용(본문 없는) AI 메시지는 표시에서 제외
                display_message_list.append({"role" : "agent", "text" : body_text, "reasoning" : reasoning_text or None})
        return {"thread_id" : thread_id, "messages" : display_message_list}

    async def truncate_thread_async(self, thread_id : str, truncate_request : TruncateThreadRequest,
                                    authorization : Optional[str]) -> Dict[str, Any]:
        # 특정 사용자 질문(0-based 순번)부터 이후 메시지를 체크포인트에서 제거한다.
        # RemoveMessage 를 add_messages 리듀서에 흘려보내 해당 메시지들을 상태에서 지운다.
        user_id = self.auth_service.require_authenticated_user_id(authorization)
        await self.auth_service.assert_thread_accessible_async(user_id, thread_id)
        if truncate_request.keep_human_message_count < 0:
            raise HTTPException(status_code = 400, detail = "INVALID KEEP HUMAN MESSAGE COUNT")

        runnable_configuration = {"configurable" : {"thread_id" : thread_id}}
        compiled_graph         = self.compiled_graph_loader()
        state_snapshot         = await compiled_graph.aget_state(runnable_configuration)
        message_list           = state_snapshot.values.get("messages", []) if state_snapshot else []

        human_message_seen_count = 0
        cut_index                = None
        for message_index, message in enumerate(message_list):
            if isinstance(message, HumanMessage):
                if human_message_seen_count == truncate_request.keep_human_message_count:
                    cut_index = message_index
                    break
                human_message_seen_count += 1
        if cut_index is None:
            # 체크포인트에 그만큼의 사용자 메시지가 없다 (실패/중단 턴으로 프론트와 어긋난 경우) → 제거할 것 없음
            print(f"THREAD TRUNCATE SKIPPED : THREAD {thread_id} - "
                  f"KEEP {truncate_request.keep_human_message_count} - HUMAN {human_message_seen_count}", flush = True)
            return {"thread_id" : thread_id, "kept_count" : len(message_list), "removed_count" : 0}

        removal_message_list = [RemoveMessage(id = message.id) for message in message_list[cut_index:]
                                if getattr(message, "id", None) is not None]
        if removal_message_list:
            await compiled_graph.aupdate_state(runnable_configuration, {"messages" : removal_message_list})

        # 잘려나간 답변들의 북마크를 정리한다. agent_index 는 위치 기반이라 절단 후 남겨두면 엉뚱한 답변을 가리키게 된다.
        # 남길 개수는 표시 규칙과 동일하게 센다 (본문 없는 도구 호출 AI 메시지는 제외).
        kept_agent_message_count = sum(
            1 for message in message_list[:cut_index]
            if type(message).__name__ in ThreadService.AGENT_MESSAGE_TYPE_NAME_TUPLE
            and ThinkTokenHelper.extract_message_texts(message)[0])
        async with self.checkpoint_connection_pool.connection() as connection:
            await connection.execute(
                ChatBookmarkQuery.DELETE_FROM_AGENT_INDEX, (kept_agent_message_count, thread_id, user_id))

        # 요약도 초기화한다 — 잘려나간 대화를 요약이 계속 가리키면 모델이 삭제된 내용을 기억한 것처럼 답한다.
        # (다음 턴에 남은 히스토리로 다시 요약이 만들어진다)
        if self.conversation_summary_repository is not None:
            await self.conversation_summary_repository.clear_summary_async(thread_id)
        print(f"THREAD TRUNCATED : THREAD {thread_id} - KEPT {cut_index} - REMOVED {len(removal_message_list)}", flush = True)
        return {"thread_id" : thread_id, "kept_count" : cut_index, "removed_count" : len(removal_message_list)}

    async def diagnose_thread_async(self, thread_id : str, authorization : Optional[str]) -> Dict[str, Any]:
        # ① 순수 체크포인트 로드 시간 : aget_state 전후를 perf_counter 로 측정한다
        user_id = self.auth_service.require_authenticated_user_id(authorization)
        await self.auth_service.assert_thread_accessible_async(user_id, thread_id)

        runnable_configuration = {"configurable" : {"thread_id" : thread_id}}
        load_started_at        = time.perf_counter()
        state_snapshot         = await self.compiled_graph_loader().aget_state(runnable_configuration)
        load_time_ms           = (time.perf_counter() - load_started_at) * 1000

        message_list : List[BaseMessage] = state_snapshot.values.get("messages", []) if state_snapshot else []
        if not message_list and (state_snapshot is None or not state_snapshot.values):
            raise HTTPException(status_code = 404, detail = f"NO CHECKPOINT STATE : {thread_id}")

        # ② 메시지 수  ③ 생각 토큰 총 바이트(KB) — 인라인 <think> + reasoning_content 합산
        think_total_byte_count = sum(ThinkTokenHelper.count_think_byte(message) for message in message_list)
        return {
            "load_time_ms"  : round(load_time_ms, 1),
            "message_count" : len(message_list),
            "think_tag_kb"  : round(think_total_byte_count / 1024, 1)
        }
