##################################################
# Vision 메시지 조립기
# 텍스트 질문 + 이미지 URL 목록을 OpenAI 멀티모달 규격의 content 블록 배열로 만든다.
#
#   [{"type": "text", "text": ...}, {"type": "image_url", "image_url": {"url": ...}}, ...]
#
# vLLM / OpenAI 계열은 이 URL 을 서버가 직접 내려받아 읽는다.
# 반면 Ollama 는 URL 을 읽지 못하고 base64 실데이터를 요구한다
# (app/llm/agent/image_attachment_interceptor.py 주석 참고).
# 그래서 VISION_IMAGE_INLINE_BASE64=true 로 두면 MinIO 에서 직접 내려받아 data URI 로 바꿔 넣는다.
##################################################

import base64
import os

from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from urllib.parse import urlparse

from common.storage.s3_helper import s3_helper


class VisionMessageBuilder:
    IMAGE_MAXIMUM_COUNT = 5   # 한 질문에 실을 수 있는 이미지 수 (컨텍스트가 이미지로 뒤덮이는 것을 막는다)

    def __init__(self, is_inline_base64 : bool = False, object_key_prefix : str = "uploads") -> None:
        # is_inline_base64 : True 면 URL 대신 실제 이미지 바이트를 base64 로 실어 보낸다
        self.is_inline_base64  = is_inline_base64
        self.object_key_prefix = object_key_prefix.strip("/")

    @staticmethod
    def create_from_environment() -> "VisionMessageBuilder":
        inline_value = os.getenv("VISION_IMAGE_INLINE_BASE64", "false").strip().lower()
        return VisionMessageBuilder(
            is_inline_base64  = inline_value in ("true", "1", "yes"),
            object_key_prefix = os.getenv("IMAGE_UPLOAD_PREFIX", "uploads"))

    def _extract_object_key(self, image_url : str) -> Optional[str]:
        # presigned URL 이든 public URL 이든 경로 안에 "{prefix}/{uuid}.{ext}" 가 들어 있다.
        # 쿼리스트링(서명)은 버리고 그 조각만 되찾아 스토리지에서 원본을 읽는다.
        try:
            path_text = urlparse(image_url).path
        except ValueError:
            return None
        marker = f"/{self.object_key_prefix}/"
        if marker not in path_text:
            return None
        return self.object_key_prefix + "/" + path_text.split(marker, 1)[1]

    def _build_image_block(self, image_url : str) -> Optional[Dict[str, Any]]:
        if not self.is_inline_base64:
            return {"type" : "image_url", "image_url" : {"url" : image_url}}

        # 인라인 모드 : 스토리지에서 직접 내려받아 data URI 로 바꾼다
        object_key = self._extract_object_key(image_url)
        if object_key is None:
            print(f"VISION IMAGE KEY NOT RESOLVED : {image_url[:120]}", flush = True)
            return None
        file_stream = s3_helper.download_fileobj(object_key)
        if file_stream is None:
            return None
        mime_type   = "image/png" if object_key.endswith(".png") else "image/jpeg"
        base64_text = base64.b64encode(file_stream.read()).decode("ascii")
        return {"type" : "image_url", "image_url" : {"url" : f"data:{mime_type};base64,{base64_text}"}}

    def build_message_content(self, message_text : str, image_url_list : Optional[List[str]]) -> Any:
        # 이미지가 없으면 문자열 그대로 돌려준다 — 텍스트 전용 대화의 형식을 바꾸지 않기 위함
        # (블록 배열로 감싸면 체크포인트에 저장되는 모양이 달라지고 기존 복원 로직이 어긋난다)
        if not image_url_list:
            return message_text

        content_block_list : List[Dict[str, Any]] = [{"type" : "text", "text" : message_text}]
        for image_url in image_url_list[:VisionMessageBuilder.IMAGE_MAXIMUM_COUNT]:
            if not isinstance(image_url, str) or not image_url.strip():
                continue
            image_block = self._build_image_block(image_url.strip())
            if image_block is not None:
                content_block_list.append(image_block)

        # 이미지를 하나도 싣지 못했으면 텍스트 전용으로 되돌린다 (빈 이미지 블록을 보내면 모델이 오류를 낸다)
        if len(content_block_list) == 1:
            return message_text
        return content_block_list
