##################################################
# 이미지 격리(Detachment)/재주입(Re-injection) 파이프라인 테스트
# - 텍스트 전용 대화 : 스토리지 호출 0회의 완전 패스스루 검증
# - Base64 이미지 블록(OpenAI/LangChain 두 형식) : 격리 → 참조 블록 치환 → 재주입 왕복 검증
# - 미들웨어 : 모델 요청에만 실데이터가 주입되고 원본 State 메시지는 불변임을 검증
# - LocalFileBinaryStorage : 저장/로드 왕복 + 경로 조작 방어 검증
#
# 실행 : .venv\Scripts\python.exe -m pytest -v
##################################################

import asyncio
import base64

import pytest

from langchain_core.messages import HumanMessage

from app.llm.agent.binary_storage               import LocalFileBinaryStorage
from app.llm.agent.image_attachment_interceptor import ImageAttachmentInterceptor
from app.llm.agent.image_reinjection_middleware import ImageReinjectionMiddleware


LARGE_IMAGE_BYTES  = b"\x89PNG-fake-image-payload" * 400   # ~9KB (임계값 4096 초과)
LARGE_BASE64_TEXT  = base64.b64encode(LARGE_IMAGE_BYTES).decode("ascii")
SMALL_BASE64_TEXT  = base64.b64encode(b"tiny").decode("ascii")


class InMemoryBinaryStorage:
    # BinaryStorageProtocol 인메모리 대역 : 저장/로드 호출 횟수까지 관측한다
    def __init__(self):
        self.binary_dictionary = {}
        self.save_call_count   = 0
        self.load_call_count   = 0

    async def save_binary_async(self, binary_data):
        self.save_call_count += 1
        reference_id = f"ref-{len(self.binary_dictionary)}"
        self.binary_dictionary[reference_id] = binary_data
        return reference_id

    async def load_binary_async(self, reference_id):
        self.load_call_count += 1
        return self.binary_dictionary[reference_id]


def _create_interceptor():
    storage = InMemoryBinaryStorage()
    return ImageAttachmentInterceptor(storage, detach_minimum_byte_count = 4096), storage


class TestTextOnlyPassThrough:
    def test_text_message_untouched_and_no_storage_call(self):
        interceptor, storage = _create_interceptor()
        message_list         = [HumanMessage(content = "이미지 없는 일반 질문")]
        detached_list        = asyncio.run(interceptor.detach_image_from_message_list_async(message_list))
        reinjected_list      = asyncio.run(interceptor.reinject_image_into_message_list_async(detached_list))
        assert detached_list[0]      is message_list[0]   # 동일 객체 그대로 통과 (복사 비용조차 없음)
        assert reinjected_list[0]    is message_list[0]
        assert storage.save_call_count == 0
        assert storage.load_call_count == 0


class TestDetachment:
    def test_openai_style_data_uri_block_detached(self):
        interceptor, storage = _create_interceptor()
        message_list = [HumanMessage(content = [
            {"type" : "text", "text" : "이 이미지 설명해줘"},
            {"type" : "image_url", "image_url" : {"url" : f"data:image/png;base64,{LARGE_BASE64_TEXT}"}}
        ])]
        detached_list   = asyncio.run(interceptor.detach_image_from_message_list_async(message_list))
        detached_blocks = detached_list[0].content
        assert detached_blocks[0] == {"type" : "text", "text" : "이 이미지 설명해줘"}      # 텍스트 블록 보존
        assert detached_blocks[1]["type"] == "image_reference"                             # 이미지 → 참조 블록
        assert detached_blocks[1]["mime_type"] == "image/png"
        assert storage.binary_dictionary[detached_blocks[1]["reference_id"]] == LARGE_IMAGE_BYTES
        assert len(str(detached_blocks)) < 1024                                            # State 직렬화 크기 KB 미만

    def test_langchain_standard_block_detached(self):
        interceptor, storage = _create_interceptor()
        message_list  = [HumanMessage(content = [{"type" : "image", "source_type" : "base64", "data" : LARGE_BASE64_TEXT, "mime_type" : "image/jpeg"}])]
        detached_list = asyncio.run(interceptor.detach_image_from_message_list_async(message_list))
        assert detached_list[0].content[0]["type"]      == "image_reference"
        assert detached_list[0].content[0]["mime_type"] == "image/jpeg"
        assert storage.save_call_count == 1

    def test_small_image_below_threshold_not_detached(self):
        interceptor, storage = _create_interceptor()
        small_block   = {"type" : "image_url", "image_url" : {"url" : f"data:image/png;base64,{SMALL_BASE64_TEXT}"}}
        detached_list = asyncio.run(interceptor.detach_image_from_message_list_async([HumanMessage(content = [small_block])]))
        assert detached_list[0].content[0] == small_block   # 임계값 미만 : 격리 이득이 없어 그대로
        assert storage.save_call_count == 0

    def test_original_message_not_mutated(self):
        interceptor, _storage = _create_interceptor()
        original_block = {"type" : "image_url", "image_url" : {"url" : f"data:image/png;base64,{LARGE_BASE64_TEXT}"}}
        message_list   = [HumanMessage(content = [original_block])]
        asyncio.run(interceptor.detach_image_from_message_list_async(message_list))
        assert message_list[0].content[0] == original_block   # 원본은 불변 (model_copy 로 새 메시지 생성)


class TestReinjectionRoundTrip:
    def test_detach_then_reinject_restores_data_uri(self):
        interceptor, _storage = _create_interceptor()
        message_list    = [HumanMessage(content = [{"type" : "image_url", "image_url" : {"url" : f"data:image/png;base64,{LARGE_BASE64_TEXT}"}}])]
        detached_list   = asyncio.run(interceptor.detach_image_from_message_list_async(message_list))
        reinjected_list = asyncio.run(interceptor.reinject_image_into_message_list_async(detached_list))
        restored_url    = reinjected_list[0].content[0]["image_url"]["url"]
        assert restored_url == f"data:image/png;base64,{LARGE_BASE64_TEXT}"   # 페이로드 무손실 왕복


class StubModelRequest:
    # 미들웨어가 사용하는 인터페이스(messages / override)만 갖춘 ModelRequest 대역
    def __init__(self, messages):
        self.messages = messages

    def override(self, **overrides):
        return StubModelRequest(overrides.get("messages", self.messages))


class TestImageReinjectionMiddleware:
    def test_model_receives_real_image_but_state_keeps_reference(self):
        interceptor, _storage = _create_interceptor()
        detached_list = asyncio.run(interceptor.detach_image_from_message_list_async(
            [HumanMessage(content = [{"type" : "image_url", "image_url" : {"url" : f"data:image/png;base64,{LARGE_BASE64_TEXT}"}}])]
        ))
        middleware     = ImageReinjectionMiddleware(interceptor)
        state_request  = StubModelRequest(messages = detached_list)
        handler_seen   = {}

        async def fake_handler(model_request):
            handler_seen["messages"] = model_request.messages
            return "model-response"

        response = asyncio.run(middleware.awrap_model_call(state_request, fake_handler))
        assert response == "model-response"
        assert handler_seen["messages"][0].content[0]["type"] == "image_url"        # 모델에게는 실데이터
        assert LARGE_BASE64_TEXT in handler_seen["messages"][0].content[0]["image_url"]["url"]
        assert state_request.messages[0].content[0]["type"] == "image_reference"    # State 는 여전히 참조만


class TestLocalFileBinaryStorage:
    def test_save_and_load_round_trip(self, tmp_path):
        storage = LocalFileBinaryStorage(str(tmp_path))

        async def round_trip_async():
            reference_id = await storage.save_binary_async(LARGE_IMAGE_BYTES)
            return reference_id, await storage.load_binary_async(reference_id)

        reference_id, loaded_bytes = asyncio.run(round_trip_async())
        assert loaded_bytes == LARGE_IMAGE_BYTES
        assert (tmp_path / f"{reference_id}.bin").exists()

    def test_path_traversal_reference_rejected(self, tmp_path):
        storage = LocalFileBinaryStorage(str(tmp_path))
        with pytest.raises(ValueError, match = "INVALID BINARY REFERENCE ID"):
            asyncio.run(storage.load_binary_async("../../etc/passwd"))
