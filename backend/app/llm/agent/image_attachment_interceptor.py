##################################################
# 이미지 격리/재주입 인터셉터
# 멀티모달 메시지에서 Base64 대용량 이미지를 감지해 외부 스토리지로 격리(Detachment)하고,
# State 에는 KB 미만의 참조 블록만 남긴다. 모델 호출 직전에는 참조를 실제 데이터로
# 복원(Re-injection)한다 — Ollama 는 URL 을 못 읽고 실제 Base64 를 요구하기 때문.
#
# [데이터 흐름]
#   detach  : 그래프 입력 직전 (라우터)      → 체크포인트에는 참조만 저장됨 (MB → KB)
#   reinject: 모델 요청 직전 (awrap_model_call) → 모델에게만 실데이터 전달, State 는 그대로
#
# [감지 대상 블록]
#   ① OpenAI 스타일   : {"type": "image_url", "image_url": {"url": "data:<mime>;base64,<payload>"}}
#   ② LangChain 표준  : {"type": "image", "source_type": "base64", "data": <payload>, "mime_type": ...}
#   격리 후 참조 블록 : {"type": "image_reference", "reference_id": <uuid>, "mime_type": ...}
#
# 텍스트 전용 메시지(content 가 str)는 어떤 변환도 없이 그대로 통과한다 (Pass-through).
##################################################

import base64

from typing import Any
from typing import Dict
from typing import List

from langchain_core.messages import BaseMessage

from app.llm.agent.binary_storage import BinaryStorageProtocol


class ImageAttachmentInterceptor:
    IMAGE_REFERENCE_BLOCK_TYPE = "image_reference"
    DATA_URI_PREFIX            = "data:"

    def __init__(self, binary_storage : BinaryStorageProtocol, detach_minimum_byte_count : int = 4096) -> None:
        # detach_minimum_byte_count : 이보다 작은 페이로드는 격리 이득이 없어 그대로 둔다
        self.binary_storage            = binary_storage
        self.detach_minimum_byte_count = detach_minimum_byte_count

    # ---------- 감지 ----------

    @staticmethod
    def _extract_base64_payload(content_block : Dict[str, Any]) -> tuple :
        # 감지되면 (base64_text, mime_type) 을, 아니면 (None, None) 을 반환한다
        if not isinstance(content_block, dict):
            return None, None
        if content_block.get("type") == "image_url":
            image_url_value = content_block.get("image_url")
            url_text        = image_url_value.get("url") if isinstance(image_url_value, dict) else image_url_value
            if isinstance(url_text, str) and url_text.startswith(ImageAttachmentInterceptor.DATA_URI_PREFIX) and ";base64," in url_text:
                header_text, base64_text = url_text.split(";base64,", 1)
                return base64_text, header_text[len(ImageAttachmentInterceptor.DATA_URI_PREFIX):] or "image/png"
        if content_block.get("type") == "image" and isinstance(content_block.get("data"), str) and content_block.get("source_type", "base64") == "base64":
            return content_block["data"], content_block.get("mime_type", "image/png")
        return None, None

    # ---------- 격리 (Detachment) ----------

    async def _detach_content_block_async(self, content_block : Any) -> Any:
        base64_text, mime_type = ImageAttachmentInterceptor._extract_base64_payload(content_block)
        if base64_text is None or len(base64_text) < self.detach_minimum_byte_count:
            return content_block
        reference_id = await self.binary_storage.save_binary_async(base64.b64decode(base64_text))
        return {"type" : ImageAttachmentInterceptor.IMAGE_REFERENCE_BLOCK_TYPE, "reference_id" : reference_id, "mime_type" : mime_type}

    async def detach_image_from_message_list_async(self, message_list : List[BaseMessage]) -> List[BaseMessage]:
        detached_message_list = []
        for message in message_list:
            if not isinstance(message.content, list):
                detached_message_list.append(message)  # 텍스트 전용 : 무비용 통과
                continue
            detached_content_list = [await self._detach_content_block_async(content_block) for content_block in message.content]
            if detached_content_list == message.content:
                detached_message_list.append(message)
            else:
                detached_message_list.append(message.model_copy(update = {"content" : detached_content_list}))
        return detached_message_list

    # ---------- 재주입 (Re-injection) ----------

    async def _reinject_content_block_async(self, content_block : Any) -> Any:
        if not (isinstance(content_block, dict) and content_block.get("type") == ImageAttachmentInterceptor.IMAGE_REFERENCE_BLOCK_TYPE):
            return content_block
        binary_data = await self.binary_storage.load_binary_async(content_block["reference_id"])
        base64_text = base64.b64encode(binary_data).decode("ascii")
        mime_type   = content_block.get("mime_type", "image/png")
        return {"type" : "image_url", "image_url" : {"url" : f"data:{mime_type};base64,{base64_text}"}}

    async def reinject_image_into_message_list_async(self, message_list : List[BaseMessage]) -> List[BaseMessage]:
        reinjected_message_list = []
        for message in message_list:
            if not isinstance(message.content, list):
                reinjected_message_list.append(message)  # 텍스트 전용 : 무비용 통과
                continue
            reinjected_content_list = [await self._reinject_content_block_async(content_block) for content_block in message.content]
            if reinjected_content_list == message.content:
                reinjected_message_list.append(message)
            else:
                reinjected_message_list.append(message.model_copy(update = {"content" : reinjected_content_list}))
        return reinjected_message_list
