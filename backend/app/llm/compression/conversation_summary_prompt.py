from typing import List
from typing import Optional


##################################################
# 대화 요약 프롬프트 템플릿
#
# 요약문은 다음 턴의 System Message 에 그대로 실려 모델의 유일한 과거 맥락이 된다.
# 그래서 "읽기 좋은 줄거리"가 아니라 "대화를 이어가는 데 필요한 사실"을 남기도록 지시한다 —
# 사용자가 밝힌 제약·선호·결정 사항이 빠지면 모델이 이미 합의한 내용을 다시 묻는다.
##################################################
class ConversationSummaryPrompt:
    SYSTEM_PROMPT = (
        "당신은 대화 기록을 압축하는 요약 전문가입니다. "
        "다음 대화를 이어갈 AI 가 맥락을 잃지 않도록 핵심만 남긴 요약문을 작성하세요.\n"
        "\n"
        "규칙 :\n"
        "- {summary_line_count} 줄 이내의 한국어 평문으로 작성한다.\n"
        "- 사용자가 밝힌 목적·제약·선호·결정 사항을 우선 남긴다.\n"
        "- 아직 해결되지 않은 질문이나 진행 중인 작업이 있으면 반드시 포함한다.\n"
        "- 인사말·감탄사·중복 표현은 버린다.\n"
        "- 요약문만 출력한다. 머리말·꼬리말·따옴표를 붙이지 않는다."
    )

    # 최종 프롬프트에 실리는 System Message. {summary} 자리에 누적 요약문이 들어간다.
    CHAT_SYSTEM_PROMPT_WITH_SUMMARY = (
        "당신은 AI 도우미입니다.\n"
        "\n"
        "[이전 대화 요약]\n"
        "{summary}\n"
        "\n"
        "위 요약은 오래된 대화를 압축한 것입니다. 이어지는 최근 대화를 참고해 자연스럽게 응답하세요."
    )

    @staticmethod
    def build_system_prompt(summary_line_count : int) -> str:
        return ConversationSummaryPrompt.SYSTEM_PROMPT.format(summary_line_count = summary_line_count)

    @staticmethod
    def build_summarization_request(previous_summary : Optional[str], conversation_text_list : List[str]) -> str:
        # 기존 요약이 있으면 [기존 요약 + 그 이후 누적된 대화] 를 함께 넘겨 하나의 새 요약으로 갱신한다.
        # 기존 요약을 빼고 새 대화만 요약하면 앞부분 맥락이 매 압축마다 조금씩 증발한다.
        section_list = []
        if previous_summary:
            section_list.append(f"[기존 요약]\n{previous_summary}")
        section_list.append("[새로 추가된 대화]\n" + "\n".join(conversation_text_list))
        section_list.append("위 내용을 하나의 요약문으로 통합해 작성하세요.")
        return "\n\n".join(section_list)

    @staticmethod
    def build_chat_system_prompt(summary : str) -> str:
        return ConversationSummaryPrompt.CHAT_SYSTEM_PROMPT_WITH_SUMMARY.format(summary = summary)
