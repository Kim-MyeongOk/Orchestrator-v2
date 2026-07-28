##################################################
# 생각 토큰(reasoning) 감지/트리밍 헬퍼
#
# 서빙 조합마다 생각 토큰이 실려 오는 자리가 다르다.
#   - 인라인      : content 안의 <think>...</think> 태그
#   - ollama      : additional_kwargs.reasoning_content
#   - google      : content 리스트 안의 thinking 블록
# 세 경로를 모두 알아보고 걷어내야 다음 턴 프롬프트가 생각 토큰으로 부풀지 않는다.
##################################################

import re

from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

from langchain_core.messages import BaseMessage


class ThinkTokenHelper:
    # <think>...</think> 인라인 태그 (일부 서빙 조합은 생각 토큰을 content 안에 인라인으로 넣는다)
    THINK_TAG_PATTERN = re.compile(r"<think>(.*?)</think>", re.DOTALL)

    @staticmethod
    def count_think_byte(message : BaseMessage) -> int:
        # 메시지 1건에서 생각 토큰이 차지하는 바이트 수를 계산한다 (체크포인트 진단용)
        think_byte_count = 0
        if isinstance(message.content, str):
            for think_text in ThinkTokenHelper.THINK_TAG_PATTERN.findall(message.content):
                think_byte_count += len(think_text.encode("utf-8"))
        reasoning_text = (message.additional_kwargs or {}).get("reasoning_content")
        if isinstance(reasoning_text, str):
            think_byte_count += len(reasoning_text.encode("utf-8"))
        return think_byte_count

    @staticmethod
    def prepare_model_input(message_list : List[BaseMessage], window_message_count : int = 20) -> List[BaseMessage]:
        # ① 트리밍 : 과거 메시지의 <think> 인라인 태그와 reasoning_content 를 제거한다
        # ② 윈도잉 : 최근 N개 메시지만 유지해 프리필 상한을 고정한다 (오래된 대화는 프롬프트에서 제외)
        slim_message_list = []
        for message in message_list[-window_message_count:]:
            updated_field_dictionary : Dict[str, Any] = {}
            if isinstance(message.content, str) and "<think>" in message.content:
                updated_field_dictionary["content"] = ThinkTokenHelper.THINK_TAG_PATTERN.sub("", message.content).strip()
            if isinstance(message.content, list) and any(
                    isinstance(content_block, dict) and content_block.get("type") == "thinking"
                    for content_block in message.content):
                # google(Gemini) : content 리스트 안의 thinking 블록 제거
                updated_field_dictionary["content"] = [
                    content_block for content_block in message.content
                    if not (isinstance(content_block, dict) and content_block.get("type") == "thinking")]
            if (message.additional_kwargs or {}).get("reasoning_content"):
                updated_field_dictionary["additional_kwargs"] = {
                    key : value for key, value in message.additional_kwargs.items() if key != "reasoning_content"}
            slim_message_list.append(
                message.model_copy(update = updated_field_dictionary) if updated_field_dictionary else message)
        return slim_message_list

    @staticmethod
    def extract_message_texts(message : BaseMessage) -> Tuple[str, str]:
        # 저장 메시지 1건에서 (본문 텍스트, 생각 텍스트) 를 추출한다
        reasoning_text = (getattr(message, "additional_kwargs", None) or {}).get("reasoning_content", "") or ""
        body_text      = ""
        if isinstance(message.content, str):
            body_text = message.content
        elif isinstance(message.content, list):
            for content_block in message.content:
                if isinstance(content_block, str):
                    body_text += content_block
                elif isinstance(content_block, dict):
                    if content_block.get("type") == "thinking":
                        reasoning_text += content_block.get("thinking", "")
                    elif content_block.get("type") == "text":
                        body_text += content_block.get("text", "")
        return body_text.strip(), reasoning_text
