from typing import Any
from typing import List
from typing import Optional

from langchain_core.messages import BaseMessage


##################################################
# 토큰 수 계산 헬퍼
#
# 정확한 토큰 수는 프로바이더(ollama / gemini / openai)마다 토크나이저가 달라 서버에서 알 수 없다.
# 모델이 get_num_tokens_from_messages 를 제공하면 그것을 쓰고, 실패하면 문자 기반 근사로 떨어진다.
# 근사값은 "절약량 표시"와 "임계치 판정"에만 쓰이므로 오차가 기능을 깨뜨리지 않는다.
##################################################
class TokenCountHelper:
    # 한글은 대략 1.5 자당 1 토큰, 영문은 4 자당 1 토큰이다. 한국어 대화 기준으로 1.8 을 쓴다.
    APPROXIMATE_CHARACTER_PER_TOKEN = 1.8
    MESSAGE_OVERHEAD_TOKEN_COUNT    = 4     # role/구분자 등 메시지 1건당 붙는 고정 비용

    @staticmethod
    def _extract_plain_text(message : BaseMessage) -> str:
        # content 가 문자열이 아닌 멀티모달(list) 인 경우 텍스트 블록만 이어붙인다
        if isinstance(message.content, str):
            return message.content
        if isinstance(message.content, list):
            text_part_list = []
            for content_block in message.content:
                if isinstance(content_block, str):
                    text_part_list.append(content_block)
                elif isinstance(content_block, dict):
                    text_part_list.append(content_block.get("text", "") or content_block.get("thinking", ""))
            return "".join(text_part_list)
        return str(message.content or "")

    @staticmethod
    def count_text_token(source_text : str) -> int:
        if not source_text:
            return 0
        return max(1, int(len(source_text) / TokenCountHelper.APPROXIMATE_CHARACTER_PER_TOKEN))

    @staticmethod
    def count_message_list_token(message_list : List[BaseMessage], chat_model : Optional[Any] = None) -> int:
        # 모델이 제공하는 토크나이저를 우선 시도한다 (프로바이더별 미지원/예외는 근사로 폴백)
        if chat_model is not None:
            try:
                return int(chat_model.get_num_tokens_from_messages(message_list))
            except Exception:
                pass
        total_token_count = 0
        for message in message_list:
            total_token_count += TokenCountHelper.count_text_token(TokenCountHelper._extract_plain_text(message))
            total_token_count += TokenCountHelper.MESSAGE_OVERHEAD_TOKEN_COUNT
        return total_token_count
