##################################################
# 참조 맥락 조립기
#
# 질문에 붙는 참조는 두 종류다.
#   ① 발췌      : 답변 본문을 드래그해 담은 문장 일부 (referenced_text)
#   ② 답변 통째 : 답변을 우클릭해 고른 것 (referenced_message_id_list, "agent-3" 형식)
#
# 최종 프롬프트는 <referenced_context> → [참조 내용] → [질문] 순으로 쌓는다.
# 조합 결과를 그대로 HumanMessage 로 저장한다 — 다음 턴에도 체크포인트에서 참조 맥락이 함께
# 복원되어야 "아까 그거"처럼 발췌를 가리키는 후속 질문이 이어진다.
##################################################

from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional

from app.llm.agent.think_token_helper import ThinkTokenHelper


class ReferenceContextBuilder:
    MESSAGE_ID_PREFIX      = "agent-"   # 답변 ID 형식 : agent-{답변 순번(0부터)}
    MESSAGE_MAXIMUM_COUNT  = 10         # 통째로 참조할 수 있는 이전 답변 개수 (기본값 : 10)
    MESSAGE_MAXIMUM_LENGTH = 4000       # 참조 답변 1건당 최대 길이 (기본값 : 4000)
    TEXT_MAXIMUM_LENGTH    = 2000       # 참조 발췌 최대 길이 — 프롬프트가 발췌로 뒤덮이는 것을 막는다

    def __init__(self, state_snapshot_loader : Callable) -> None:
        # state_snapshot_loader(thread_id) -> awaitable(StateSnapshot)
        # 그래프 캐시를 그대로 들고 오면 순환 의존이 생기므로 "체크포인트를 읽는 방법"만 주입받는다.
        self.state_snapshot_loader = state_snapshot_loader

    @staticmethod
    def parse_agent_index(referenced_message_id : str) -> Optional[int]:
        # "agent-3" → 3. 형식이 어긋나면 None 을 돌려주고 호출부가 조용히 건너뛴다.
        if not isinstance(referenced_message_id, str):
            return None
        if not referenced_message_id.startswith(ReferenceContextBuilder.MESSAGE_ID_PREFIX):
            return None
        index_text = referenced_message_id[len(ReferenceContextBuilder.MESSAGE_ID_PREFIX):]
        if not index_text.isdigit():
            return None
        return int(index_text)

    async def collect_referenced_message_list_async(self, thread_id : str,
                                                    referenced_message_id_list : List[str]) -> List[Dict[str, Any]]:
        # 요청받은 답변 ID 들을 체크포인트 본문으로 바꿔 돌려준다.
        #
        # 유효하지 않은 ID(형식 오류·이미 사라진 순번)는 예외를 던지지 않고 건너뛴다.
        # 질문 수정으로 대화가 잘리거나 다른 기기에서 방을 지우면 프론트가 들고 있던 순번이 실제로 없어질 수 있는데,
        # 그때 질문 전체를 실패시키면 사용자는 이유를 알 수 없는 오류만 보게 된다.
        requested_index_list = []
        for referenced_message_id in referenced_message_id_list[:ReferenceContextBuilder.MESSAGE_MAXIMUM_COUNT]:
            agent_index = ReferenceContextBuilder.parse_agent_index(referenced_message_id)
            if agent_index is None or agent_index in requested_index_list:
                continue
            requested_index_list.append(agent_index)
        if not requested_index_list:
            return []

        try:
            state_snapshot = await self.state_snapshot_loader(thread_id)
        except Exception as exception:
            # 체크포인트를 못 읽어도 질문 자체는 진행시킨다 (참조만 빠진다)
            print(f"REFERENCED MESSAGE LOOKUP FAILED : THREAD {thread_id} - {exception}", flush = True)
            return []

        # 표시용 순번과 같은 규칙으로 답변만 추린다 (본문 없는 도구 호출 메시지는 제외)
        agent_text_list = []
        for message in (state_snapshot.values.get("messages", []) if state_snapshot else []):
            if type(message).__name__ not in ("AIMessage", "AIMessageChunk"):
                continue
            body_text, _reasoning_text = ThinkTokenHelper.extract_message_texts(message)
            if body_text:
                agent_text_list.append(body_text)

        # 사용자가 고른 순서가 아니라 대화 순서대로 넣는다 — 모델이 시간 흐름대로 읽는 편이 자연스럽다
        referenced_message_list = []
        for agent_index in sorted(requested_index_list):
            if agent_index >= len(agent_text_list):
                continue
            referenced_message_list.append({
                "agent_index" : agent_index,
                "text"        : agent_text_list[agent_index][:ReferenceContextBuilder.MESSAGE_MAXIMUM_LENGTH]
            })
        return referenced_message_list

    @staticmethod
    def build_context_block(referenced_message_list : List[Dict[str, Any]]) -> str:
        # 통째로 고른 답변들을 <referenced_context> 태그로 묶는다.
        # 태그로 감싸는 이유 : 질문 본문과 참조 자료의 경계를 모델이 확실히 구분하게 하려는 것이다.
        if not referenced_message_list:
            return ""
        block_line_list = ["<referenced_context>"]
        for referenced_message in referenced_message_list:
            block_line_list.append(f"[답변 #{referenced_message['agent_index'] + 1}]")
            block_line_list.append(referenced_message["text"])
        block_line_list.append("</referenced_context>")
        return "\n".join(block_line_list)

    @staticmethod
    def build_message_text(message : str, referenced_text : Optional[str], referenced_context_block : str = "") -> str:
        # 참조가 있으면 <referenced_context>(답변 통째로) → [참조 내용](드래그 발췌) → [질문] 순으로 조합한다.
        trimmed_reference = (referenced_text or "").strip()
        if not trimmed_reference and not referenced_context_block:
            return message

        composed_section_list = []
        if referenced_context_block:
            composed_section_list.append(referenced_context_block)
        if trimmed_reference:
            composed_section_list.append(
                f"[참조 내용]: {trimmed_reference[:ReferenceContextBuilder.TEXT_MAXIMUM_LENGTH]}")
        composed_section_list.append(f"[질문]: {message}")
        return "\n".join(composed_section_list)
