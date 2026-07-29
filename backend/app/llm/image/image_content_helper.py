##################################################
# 멀티모달 메시지 본문 헬퍼
# VisionMessageBuilder 가 만든 블록 구조를 되돌려 읽는다.
#   [{"type": "text", "text": ...}, {"type": "image_url", "image_url": {"url": ...}}, ...]
##################################################

from typing import Any
from typing import List

class ImageContentHelper:
    IMAGE_BLOCK_TYPE_SET = {"image_url", "image"}
    # 이미지를 걷어내면 "이거 뭐야?" 같은 질문만 남아 모델이 맥락을 잃는다.
    # 그 자리에 무엇이 있었는지 알려 준다 (사용자에게는 보이지 않고 모델 프롬프트에만 들어간다)
    #
    # ⚠️ 문구가 중요하다. "이미지를 지원하지 않는다"고만 쓰면 모델이 "저는 이미지를 볼 수 없습니다"로
    #    거절해 버린다 — 비전 모델이 이미 설명해 둔 내용이 대화에 있어도 쓰지 않는다.
    #    그래서 설명이 있으면 그 내용을 이미지 자리에 그대로 실어 준다.
    REMOVED_IMAGE_NOTICE_TEXT = "[첨부 이미지는 현재 모델이 이미지를 지원하지 않아 생략되었습니다]"
    IMAGE_DESCRIPTION_TEMPLATE = (
        "[첨부 이미지 — 이미지 파일 자체는 제외되었지만, 아래는 비전 모델이 이 이미지를 보고 분석한 설명이다.\n"
        " 이 설명을 이미지를 직접 본 것과 동일한 근거로 삼아 답하라. 이미지를 볼 수 없다고 답하지 말 것.]\n"
        "{description_text}")

    @staticmethod
    def _is_image_block(content_block : Any) -> bool:
        return isinstance(content_block, dict) and content_block.get("type") in ImageContentHelper.IMAGE_BLOCK_TYPE_SET

    @staticmethod
    def has_image_block(message_content : Any) -> bool:
        if not isinstance(message_content, list):
            return False
        return any(ImageContentHelper._is_image_block(content_block) for content_block in message_content)

    @staticmethod
    def build_replacement_text(description_text : str = "") -> str:
        # 이미지 자리에 넣을 텍스트. 비전 모델이 남긴 설명이 있으면 그것을 근거로 실어 준다
        if description_text and description_text.strip():
            return ImageContentHelper.IMAGE_DESCRIPTION_TEMPLATE.format(description_text = description_text.strip())
        return ImageContentHelper.REMOVED_IMAGE_NOTICE_TEXT

    @staticmethod
    def strip_image_block(message_content : Any, description_text : str = "") -> Any:
        # 이미지 블록만 걷어낸다. 남은 것이 텍스트 하나뿐이면 평범한 문자열로 되돌린다
        # (블록 리스트를 유지하면 일부 프로바이더가 멀티모달 요청으로 오해한다)
        if not ImageContentHelper.has_image_block(message_content):
            return message_content

        kept_block_list  = [content_block for content_block in message_content
                            if not ImageContentHelper._is_image_block(content_block)]
        replacement_text = ImageContentHelper.build_replacement_text(description_text)

        # 마지막 텍스트 블록 뒤에 대체 문구를 덧붙인다
        last_text_index = next((block_index for block_index in reversed(range(len(kept_block_list)))
                                if isinstance(kept_block_list[block_index], dict) and kept_block_list[block_index].get("type") == "text"), None)
        if last_text_index is None:
            # 텍스트가 아예 없던 경우(이미지만 보낸 질문)는 대체 문구만 남긴다
            return replacement_text

        last_text_block                 = kept_block_list[last_text_index]
        kept_block_list[last_text_index] = {**last_text_block,
                                            "text" : f"{last_text_block.get('text', '')}\n{replacement_text}".strip()}

        # 남은 것이 텍스트 하나뿐이면 평범한 문자열로 되돌린다
        if len(kept_block_list) == 1:
            return kept_block_list[0]["text"]
        return kept_block_list

    @staticmethod
    def limit_image_block_list(message_list : List[Any], image_maximum_count : int) -> List[Any]:
        # 최신 이미지 N장만 남기고 오래된 것부터 걷어낸다.
        # llama3.2-vision 은 한 요청에 1장만 지원해서, 대화가 이어질수록 옛 이미지가 쌓여
        # 400 "this model only supports one image" 로 그 방이 막힌다.
        # (원본 메시지는 그대로 둔다 — 체크포인트 보존)
        keep_index_set = set()
        seen_image_count = 0
        for message_index in reversed(range(len(message_list))):
            message_content = getattr(message_list[message_index], "content", None)
            if not ImageContentHelper.has_image_block(message_content):
                continue
            if seen_image_count < image_maximum_count:
                keep_index_set.add(message_index)
                seen_image_count += sum(1 for content_block in message_content
                                        if ImageContentHelper._is_image_block(content_block))

        limited_message_list = []
        for message_index, message in enumerate(message_list):
            message_content = getattr(message, "content", None)
            if message_index in keep_index_set or not ImageContentHelper.has_image_block(message_content):
                limited_message_list.append(message)
                continue
            # 걷어내는 옛 이미지도 설명을 남겨 둬야 "아까 그 사진" 같은 질문이 이어진다
            description_text = ImageContentHelper._find_following_answer_text(message_list, message_index)
            limited_message_list.append(message.model_copy(
                update = {"content" : ImageContentHelper.strip_image_block(message_content, description_text)}))
        return limited_message_list

    @staticmethod
    def _find_following_answer_text(message_list : List[Any], image_message_index : int) -> str:
        # 이미지 질문 바로 뒤에 온 비전 모델의 답변을 찾는다 — 그 답변이 곧 이 이미지의 설명이다
        for message in message_list[image_message_index + 1:]:
            if getattr(message, "type", None) != "ai":
                continue
            message_content = getattr(message, "content", None)
            if isinstance(message_content, str):
                return message_content
            if isinstance(message_content, list):
                return "".join(content_block.get("text", "") for content_block in message_content
                               if isinstance(content_block, dict) and content_block.get("type") == "text")
            return ""
        return ""

    @staticmethod
    def strip_image_block_list(message_list : List[Any]) -> List[Any]:
        # 이미지가 섞인 메시지만 골라 새 객체로 바꾼다 (원본 메시지는 그대로 둔다 — 체크포인트 보존).
        # 비전 모델이 이미 설명해 둔 이미지는 그 설명을 이미지 자리에 실어, 텍스트 모델이
        # "이미지를 볼 수 없습니다"로 거절하지 않고 지난 대화를 근거로 이어가게 한다.
        stripped_message_list = []
        for message_index, message in enumerate(message_list):
            message_content = getattr(message, "content", None)
            if not ImageContentHelper.has_image_block(message_content):
                stripped_message_list.append(message)
                continue
            description_text = ImageContentHelper._find_following_answer_text(message_list, message_index)
            stripped_message_list.append(message.model_copy(
                update = {"content" : ImageContentHelper.strip_image_block(message_content, description_text)}))
        return stripped_message_list
