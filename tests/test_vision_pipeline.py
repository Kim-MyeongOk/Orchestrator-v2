##################################################
# MinIO 업로드 → Presigned 썸네일 → Vision 추론 E2E 파이프라인 테스트
#
# 브라우저에서 이미지를 드래그앤드롭/첨부했을 때 실제로 일어나는 순서를 그대로 따라간다.
#   ① POST /api/upload           : 업로드 → MinIO 저장 → presigned URL 발급 (200)
#   ② presigned URL 로 GET       : 웹 화면 썸네일이 뜨는지 (브라우저 <img src> 와 동일한 요청)
#   ③ VisionMessageBuilder       : MinIO 에서 되읽어 base64 인라인 (Ollama 는 URL 을 못 읽는다)
#   ④ llama3.2-vision 추론       : 이미지 내용을 실제로 읽어내는지
#   그리고 예외 경로 : 400(형식/빈 파일) · 413(용량) · 401(인증)
#
# [실행]
#   .venv\Scripts\python.exe -m pytest tests/test_vision_pipeline.py -v
#
# [의존 인프라] — 없으면 해당 테스트는 skip 되고 나머지는 그대로 돈다
#   MinIO  : http://s3.samsung.com:9000  (hosts 에 127.0.0.1 매핑)
#   Ollama : http://localhost:11434 + llama3.2-vision  (없으면 ④만 skip)
#
# 인프라를 건드리는 테스트라 업로드한 객체는 각 테스트 종료 시 반드시 지운다.
##################################################

import base64
import io
import os
import sys
import urllib.error
import urllib.request

import pytest

from dotenv import load_dotenv

# s3_helper 는 임포트 시점에 환경변수를 읽는다. 그래서 어떤 임포트보다 먼저 .env 를 올려야 한다.
# (테스트 프로세스에 남아 있는 터미널 환경변수가 .env 를 이기지 않도록 override = True 로 강제한다 —
#  운영 코드에서는 환경변수가 정본이지만, 테스트는 항상 .env 가 가리키는 곳을 봐야 결과가 재현된다)
load_dotenv(".env", override = True)

from app.llm.image.image_upload_service   import ImageUploadService     # noqa: E402
from app.llm.image.vision_message_builder import VisionMessageBuilder   # noqa: E402
from common.storage.s3_helper             import s3_helper              # noqa: E402


# ⚠️ 이 모델은 Ollama 0.24.x 에서만 돈다 (0.30.0+ 는 mllama 아키텍처를 버렸다).
# 0.30 이상에서 이 테스트가 깨지면 파이프라인이 아니라 Ollama 버전을 의심해야 한다.
VISION_MODEL_KEY   = "llama3_2_vision"
VISION_MODEL_NAME  = "llama3.2-vision"
HTTP_TIMEOUT       = 15
INFERENCE_TIMEOUT  = 300


##################################################
# 테스트 픽스처 : 판별 가능한 이미지
##################################################

def _create_recognizable_png() -> bytes:
    # 모델이 "무엇을 봤는지" 말로 확인할 수 있어야 추론 성공을 판정할 수 있다.
    # 단색 1x1 로는 판정이 불가능하므로 색·도형·글자가 뚜렷한 이미지를 만든다.
    from PIL import Image
    from PIL import ImageDraw

    image = Image.new("RGB", (480, 240), (200, 30, 30))       # 빨간 배경
    draw  = ImageDraw.Draw(image)
    draw.ellipse((30, 60, 150, 180), fill = (30, 60, 200))    # 파란 원
    draw.text((200, 105), "HELLO", fill = (255, 255, 255))    # 흰 글자

    buffer = io.BytesIO()
    image.save(buffer, format = "PNG")
    return buffer.getvalue()


def _create_minimal_png() -> bytes:
    # 업로드 자체만 확인하는 경로용 최소 PNG (1x1)
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c63f8cfc00000030101"
        "0018dd8db00000000049454e44ae426082")


##################################################
# 인프라 가용성 : 없으면 skip (테스트가 인프라 사정으로 "실패"하면 안 된다)
##################################################

def _is_minio_reachable() -> bool:
    try:
        s3_helper.s3_client.list_buckets()
        return True
    except Exception:
        return False


def _is_vision_model_available() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout = 5) as response:
            import json
            model_name_list = [entry["name"] for entry in json.loads(response.read()).get("models", [])]
        return any(name.startswith(VISION_MODEL_NAME) for name in model_name_list)
    except Exception:
        return False


requires_minio  = pytest.mark.skipif(not _is_minio_reachable(),
                                     reason = "MinIO 에 연결할 수 없습니다 (S3_ENDPOINT_URL 확인)")
requires_vision = pytest.mark.skipif(not _is_vision_model_available(),
                                     reason = f"Ollama {VISION_MODEL_NAME} 을 찾을 수 없습니다")


@pytest.fixture
def upload_service():
    return ImageUploadService.create_from_environment()


@pytest.fixture
def uploaded_object_key_list():
    # 테스트가 남긴 객체를 반드시 지운다. 실패로 중단돼도 지워지도록 yield 뒤에서 정리한다.
    object_key_list = []
    yield object_key_list
    for object_key in object_key_list:
        try:
            s3_helper.delete_file(object_key)
        except Exception:
            pass


##################################################
# ① 설정 : 어느 스토리지를 바라보는지 (목 서버 오인 방지)
##################################################

class TestStorageConfiguration:
    def test_bucket_name_is_configured(self):
        # 비어 있으면 boto3 안쪽에서 TypeError 로 터져 원인을 알기 어렵다
        assert s3_helper.bucket_name, "S3_BUCKET_NAME 이 비어 있습니다 (.env 확인)"

    def test_endpoint_is_not_mock_server(self):
        # 목(moto) 서버를 바라본 채 통과하면 "성공했는데 실제 저장소는 비어 있는" 사고가 난다
        endpoint_url = s3_helper.endpoint_url or ""
        assert "5599" not in endpoint_url, (
            f"목 서버를 바라보고 있습니다 : {endpoint_url}\n"
            "터미널 환경변수 S3_ENDPOINT_URL 을 제거하고 백엔드를 재기동하세요.")

    def test_configuration_summary_is_printable(self, upload_service):
        summary_text = upload_service.describe_storage_configuration()
        assert "endpoint=" in summary_text and "bucket=" in summary_text


##################################################
# ② 업로드 : 정상 경로 + 예외 경로(400 / 413)
##################################################

class TestImageUploadValidation:
    def test_allowed_content_type(self, upload_service):
        for content_type in ("image/png", "image/jpeg", "image/webp", "image/gif"):
            assert upload_service.is_allowed_content_type(content_type)

    def test_rejected_content_type(self, upload_service):
        # svg 는 스크립트를 품을 수 있어 의도적으로 제외했다
        for content_type in ("text/plain", "application/pdf", "image/svg+xml", "", None):
            assert not upload_service.is_allowed_content_type(content_type)

    def test_content_type_with_charset_parameter(self, upload_service):
        # 브라우저가 "image/png; charset=binary" 처럼 보내도 형식만 보고 판정해야 한다
        assert upload_service.is_allowed_content_type("image/png; charset=binary")

    def test_object_key_is_uuid_based(self, upload_service):
        # 원본 파일명을 그대로 쓰면 경로 조작·덮어쓰기·한글 깨짐이 한꺼번에 따라온다
        first_key  = upload_service.build_object_key("image/png")
        second_key = upload_service.build_object_key("image/png")
        assert first_key != second_key
        assert first_key.startswith(f"{upload_service.object_key_prefix}/")
        assert first_key.endswith(".png")

    def test_object_key_extension_follows_content_type(self, upload_service):
        assert upload_service.build_object_key("image/jpeg").endswith(".jpg")
        assert upload_service.build_object_key("image/webp").endswith(".webp")
        # 알 수 없는 형식은 기본 확장자로 떨어진다 (형식 검사는 별도 단계에서 막는다)
        assert upload_service.build_object_key("application/octet-stream").endswith(".png")

    def test_maximum_byte_count_is_positive(self, upload_service):
        assert upload_service.maximum_byte_count > 0


@requires_minio
class TestMinioUploadRoundTrip:
    def test_upload_and_presigned_url_round_trip(self, upload_service, uploaded_object_key_list):
        png_bytes  = _create_minimal_png()
        object_key = upload_service.build_object_key("image/png")

        assert upload_service.upload_image(io.BytesIO(png_bytes), object_key, "image/png") is True
        uploaded_object_key_list.append(object_key)

        # ── 브라우저 썸네일과 동일한 경로 : presigned URL 을 그대로 GET 한다
        image_url = upload_service.build_image_url(object_key)
        assert image_url, "presigned URL 발급 실패"

        with urllib.request.urlopen(image_url, timeout = HTTP_TIMEOUT) as response:
            downloaded_bytes = response.read()
            assert response.status == 200
            # ContentType 이 실려야 브라우저가 내려받지 않고 <img> 로 렌더링한다
            assert response.headers.get("Content-Type") == "image/png"
        assert downloaded_bytes == png_bytes, "업로드한 바이트와 내려받은 바이트가 다릅니다"

    def test_uploaded_object_appears_in_bucket_listing(self, upload_service, uploaded_object_key_list):
        object_key = upload_service.build_object_key("image/png")
        upload_service.upload_image(io.BytesIO(_create_minimal_png()), object_key, "image/png")
        uploaded_object_key_list.append(object_key)

        assert object_key in s3_helper.list_files(upload_service.object_key_prefix + "/")

    def test_deleted_object_url_returns_error(self, upload_service):
        # Lifecycle 로 객체가 만료된 뒤의 상황과 같다 — 링크는 살아 있어도 객체가 없으면 404 다
        object_key = upload_service.build_object_key("image/png")
        upload_service.upload_image(io.BytesIO(_create_minimal_png()), object_key, "image/png")
        image_url = upload_service.build_image_url(object_key)
        s3_helper.delete_file(object_key)

        with pytest.raises(urllib.error.HTTPError) as error_info:
            urllib.request.urlopen(image_url, timeout = HTTP_TIMEOUT)
        assert error_info.value.code == 404


##################################################
# ③ Vision 메시지 조립 : URL 모드 / base64 인라인 모드
##################################################

class TestVisionMessageBuilding:
    def test_text_only_message_stays_string(self):
        # 이미지가 없으면 문자열 그대로 둔다. 블록 배열로 감싸면 체크포인트 저장 형태가 달라져
        # 기존 대화 복원 로직이 어긋난다.
        builder = VisionMessageBuilder(is_inline_base64 = False)
        assert builder.build_message_content("이미지 없는 질문", []) == "이미지 없는 질문"
        assert builder.build_message_content("이미지 없는 질문", None) == "이미지 없는 질문"

    def test_url_mode_passes_url_through(self):
        builder = VisionMessageBuilder(is_inline_base64 = False)
        content = builder.build_message_content("설명해줘", ["http://example.com/uploads/a.png"])

        assert [block["type"] for block in content] == ["text", "image_url"]
        assert content[0]["text"] == "설명해줘"
        assert content[1]["image_url"]["url"] == "http://example.com/uploads/a.png"

    def test_image_count_is_capped(self):
        builder      = VisionMessageBuilder(is_inline_base64 = False)
        many_url_list = ["http://example.com/uploads/a.png"] * 20
        content      = builder.build_message_content("설명해줘", many_url_list)

        # 텍스트 블록 1개 + 이미지 상한
        assert len(content) - 1 == VisionMessageBuilder.IMAGE_MAXIMUM_COUNT

    def test_blank_urls_are_ignored(self):
        builder = VisionMessageBuilder(is_inline_base64 = False)
        # 실을 이미지가 하나도 없으면 텍스트 전용으로 되돌린다 (빈 이미지 블록은 모델이 거부한다)
        assert builder.build_message_content("설명해줘", ["", "   ", None]) == "설명해줘"

    def test_inline_mode_skips_unresolvable_url(self):
        # 키를 못 찾으면 그 이미지만 건너뛴다 — 질문 전체를 실패시키지 않는다
        builder = VisionMessageBuilder(is_inline_base64 = True, object_key_prefix = "uploads")
        assert builder.build_message_content("설명해줘", ["http://x/other/a.png"]) == "설명해줘"


@requires_minio
class TestVisionInlineConversion:
    def test_inline_mode_converts_minio_url_to_data_uri(self, upload_service, uploaded_object_key_list):
        # Ollama 는 URL 을 읽지 못하고 base64 실데이터를 요구한다
        # (langchain_ollama : "Image data only supported through in-line base64 format.")
        png_bytes  = _create_minimal_png()
        object_key = upload_service.build_object_key("image/png")
        upload_service.upload_image(io.BytesIO(png_bytes), object_key, "image/png")
        uploaded_object_key_list.append(object_key)

        image_url = upload_service.build_image_url(object_key)
        builder   = VisionMessageBuilder(is_inline_base64 = True,
                                         object_key_prefix = upload_service.object_key_prefix)
        content   = builder.build_message_content("설명해줘", [image_url])

        inlined_url = content[1]["image_url"]["url"]
        assert inlined_url.startswith("data:image/png;base64,")
        # MinIO 에서 되읽은 바이트가 원본과 같아야 모델이 같은 그림을 본다
        assert base64.b64decode(inlined_url.split(",", 1)[1]) == png_bytes


##################################################
# ④ 실제 추론 : 비전 모델이 이미지를 읽어내는가
##################################################

@requires_minio
@requires_vision
class TestVisionInferenceEndToEnd:
    def test_model_describes_uploaded_image(self, upload_service, uploaded_object_key_list):
        from app.llm.agent.chat_model_factory import ChatModelFactory
        from app.llm.agent.model_catalog      import ModelCatalog
        from langchain_core.messages          import HumanMessage

        # ── ① 업로드 (브라우저 첨부와 동일)
        png_bytes  = _create_recognizable_png()
        object_key = upload_service.build_object_key("image/png")
        assert upload_service.upload_image(io.BytesIO(png_bytes), object_key, "image/png") is True
        uploaded_object_key_list.append(object_key)

        # ── ② presigned URL (화면 썸네일)
        image_url = upload_service.build_image_url(object_key)
        assert image_url

        # ── ③ base64 인라인 조립
        builder = VisionMessageBuilder(is_inline_base64 = True,
                                       object_key_prefix = upload_service.object_key_prefix)
        content = builder.build_message_content(
            "이 이미지에 무엇이 보이나요? 색깔과 글자를 한국어로 짧게 말해주세요.", [image_url])
        assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")

        # ── ④ 추론
        # 생각 강도를 함께 넘긴다 : UI 의 생각 정도가 thinking 미지원 모델을 깨뜨리던 회귀를 E2E 에서도 막는다
        model_configuration = ModelCatalog.load_default().create_model_configuration(VISION_MODEL_KEY, reasoning_effort = "medium")
        chat_model          = ChatModelFactory.create(model_configuration)
        assert chat_model.reasoning is False, \
            "llama3.2-vision 은 thinking 을 지원하지 않습니다 (models.yaml 의 reasoning_enabled 확인)"
        response   = chat_model.invoke([HumanMessage(content = content)])
        answer_text = str(response.content)

        assert answer_text.strip(), "모델이 빈 응답을 돌려주었습니다"

        # 이미지를 실제로 봤다면 색이나 글자 중 하나는 반드시 언급된다.
        # (표현이 모델마다 달라 여러 후보를 둔다 — 문장 전체를 비교하면 테스트가 쉽게 깨진다)
        recognition_keyword_list = ["빨강", "빨간", "red", "파랑", "파란", "blue", "HELLO", "hello", "원", "circle"]
        matched_keyword_list     = [keyword for keyword in recognition_keyword_list if keyword in answer_text]
        assert matched_keyword_list, (
            "모델이 이미지를 인식하지 못한 것으로 보입니다.\n"
            f"응답 : {answer_text[:300]}")

    def test_text_only_question_still_works(self):
        # 이미지가 없는 질문은 멀티모달 경로를 타지 않고 그대로 동작해야 한다 (회귀 방지)
        from app.llm.agent.chat_model_factory import ChatModelFactory
        from app.llm.agent.model_catalog      import ModelCatalog
        from langchain_core.messages          import HumanMessage

        builder = VisionMessageBuilder(is_inline_base64 = True)
        content = builder.build_message_content("1 더하기 1 은 얼마인가요? 숫자만 답하세요.", [])
        assert isinstance(content, str)

        chat_model = ChatModelFactory.create(
            ModelCatalog.load_default().create_model_configuration(VISION_MODEL_KEY))
        response = chat_model.invoke([HumanMessage(content = content)])
        assert "2" in str(response.content)


##################################################
# ④-2 생각 강도 오버라이드 : thinking 미지원 모델을 깨뜨리면 안 된다
##################################################

class TestReasoningOverrideSafety:
    # 카탈로그의 reasoning_enabled=False 는 "이 모델은 thinking 을 못 쓴다"는 선언이다.
    # UI 의 생각 정도(low/medium/high)가 이를 덮어쓰면 Ollama 가 400 을 던져
    # ("...does not support thinking") 턴이 통째로 실패한다.
    @staticmethod
    def _create_ollama_configuration(reasoning_enabled, reasoning_effort):
        from app.llm.agent.model_configuration import ModelConfiguration
        return ModelConfiguration(
            provider          = "ollama",
            model_name        = "any-model",
            reasoning_enabled = reasoning_enabled,
            reasoning_effort  = reasoning_effort)

    @pytest.mark.parametrize("reasoning_effort", ["low", "medium", "high"])
    def test_effort_cannot_enable_thinking_on_unsupported_model(self, reasoning_effort):
        from app.llm.agent.chat_model_factory import ChatModelFactory

        chat_model = ChatModelFactory.create(
            TestReasoningOverrideSafety._create_ollama_configuration(False, reasoning_effort))
        assert chat_model.reasoning is False, (
            f"생각 정도 '{reasoning_effort}' 가 reasoning_enabled=False 를 덮어썼습니다. "
            "thinking 미지원 모델에서 400 이 발생합니다.")

    @pytest.mark.parametrize("reasoning_effort", ["low", "medium", "high"])
    def test_effort_still_applies_when_thinking_is_allowed(self, reasoning_effort):
        # 반대 방향 회귀 방지 : 끄라고 선언하지 않은 모델은 생각 강도가 그대로 전달돼야 한다
        from app.llm.agent.chat_model_factory import ChatModelFactory

        for reasoning_enabled in (True, None):
            chat_model = ChatModelFactory.create(
                TestReasoningOverrideSafety._create_ollama_configuration(reasoning_enabled, reasoning_effort))
            assert chat_model.reasoning == reasoning_effort

    def test_model_default_is_kept_when_nothing_is_specified(self):
        from app.llm.agent.chat_model_factory import ChatModelFactory

        chat_model = ChatModelFactory.create(
            TestReasoningOverrideSafety._create_ollama_configuration(None, None))
        assert chat_model.reasoning is None


##################################################
# ④-3 비전 미지원 모델 : 이미지 블록을 프롬프트에서 걷어낸다
##################################################

class TestImageStrippingForNonVisionModel:
    # 한 번 이미지를 붙인 스레드는 그 블록이 체크포인트에 남아 매 턴 다시 실려 나간다.
    # 모델을 비전 미지원으로 바꾸면 400 "this model does not support image input" 으로
    # 그 방이 통째로 막히므로, 모델에 보내는 프롬프트에서만 이미지를 걷어내야 한다.
    IMAGE_BLOCK = {"type" : "image_url", "image_url" : {"url" : "data:image/png;base64,AAAA"}}

    def test_text_and_image_keeps_text_and_notes_removal(self):
        from app.llm.image.image_content_helper import ImageContentHelper

        stripped_content = ImageContentHelper.strip_image_block(
            [{"type" : "text", "text" : "이거 뭐야?"}, TestImageStrippingForNonVisionModel.IMAGE_BLOCK])

        assert isinstance(stripped_content, str), "블록이 하나만 남으면 평문으로 되돌려야 한다"
        assert "이거 뭐야?" in stripped_content
        assert ImageContentHelper.REMOVED_IMAGE_NOTICE_TEXT in stripped_content
        assert "base64" not in stripped_content

    def test_image_only_message_becomes_notice(self):
        from app.llm.image.image_content_helper import ImageContentHelper

        stripped_content = ImageContentHelper.strip_image_block([TestImageStrippingForNonVisionModel.IMAGE_BLOCK])
        assert stripped_content == ImageContentHelper.REMOVED_IMAGE_NOTICE_TEXT

    def test_plain_text_is_untouched(self):
        from app.llm.image.image_content_helper import ImageContentHelper

        assert ImageContentHelper.strip_image_block("그냥 텍스트") == "그냥 텍스트"
        assert ImageContentHelper.has_image_block("그냥 텍스트") is False

    def test_original_message_is_not_mutated(self):
        # 체크포인트 원본이 바뀌면 비전 모델로 되돌렸을 때 이미지가 사라진다
        from app.llm.image.image_content_helper import ImageContentHelper
        from langchain_core.messages            import HumanMessage

        original_message_list = [HumanMessage(content = [{"type" : "text", "text" : "이거 뭐야?"},
                                                         TestImageStrippingForNonVisionModel.IMAGE_BLOCK])]
        stripped_message_list = ImageContentHelper.strip_image_block_list(original_message_list)

        assert ImageContentHelper.has_image_block(original_message_list[0].content) is True, "원본이 훼손되었습니다"
        assert ImageContentHelper.has_image_block(stripped_message_list[0].content) is False

    def test_catalog_declares_vision_support(self):
        from app.llm.agent.model_catalog import ModelCatalog

        model_catalog = ModelCatalog.load_default()
        if model_catalog is None:
            pytest.skip("모델 카탈로그(config/models.yaml)가 없습니다")

        assert model_catalog.create_model_configuration(VISION_MODEL_KEY).vision_enabled is True
        assert model_catalog.create_model_configuration("gpt_oss_120b").vision_enabled is False, \
            "gpt-oss 는 capabilities 에 vision 이 없습니다 (models.yaml 의 vision_enabled 확인)"


##################################################
# ⑤ HTTP 엔드포인트 : 400 / 413 / 401 예외 응답
##################################################

@requires_minio
class TestUploadEndpointErrorHandling:
    # 실행 중인 서버에 의존하지 않도록, server.py 의 업로드 검증 흐름과 동일한 앱을 그 자리에서 만든다.
    # (인증은 별도 테스트에서 다루므로 여기서는 분리한다)
    @staticmethod
    def _create_test_client(upload_service):
        import asyncio

        from fastapi                 import FastAPI
        from fastapi                 import File
        from fastapi                 import HTTPException
        from fastapi                 import UploadFile
        from fastapi.testclient      import TestClient

        application = FastAPI()

        @application.post("/api/upload")
        async def upload_image(file : UploadFile = File(...)):
            if not upload_service.is_allowed_content_type(file.content_type):
                raise HTTPException(status_code = 400, detail = "이미지 파일만 업로드할 수 있습니다. (png / jpeg / webp / gif)")
            file_bytes = await file.read()
            if len(file_bytes) == 0:
                raise HTTPException(status_code = 400, detail = "빈 파일입니다.")
            if len(file_bytes) > upload_service.maximum_byte_count:
                maximum_megabyte = upload_service.maximum_byte_count / (1024 * 1024)
                raise HTTPException(status_code = 413, detail = f"이미지가 너무 큽니다. (최대 {maximum_megabyte:.0f}MB)")
            object_key = upload_service.build_object_key(file.content_type)
            if not await asyncio.to_thread(upload_service.upload_image, io.BytesIO(file_bytes), object_key, file.content_type):
                raise HTTPException(status_code = 502, detail = "이미지 저장소에 업로드하지 못했습니다.")
            image_url = await asyncio.to_thread(upload_service.build_image_url, object_key)
            return {"object_key" : object_key, "image_url" : image_url,
                    "content_type" : file.content_type, "byte_count" : len(file_bytes)}

        return TestClient(application)

    def test_valid_image_returns_200(self, upload_service, uploaded_object_key_list):
        client   = TestUploadEndpointErrorHandling._create_test_client(upload_service)
        response = client.post("/api/upload",
                               files = {"file" : ("shot.png", _create_minimal_png(), "image/png")})

        assert response.status_code == 200
        payload = response.json()
        uploaded_object_key_list.append(payload["object_key"])

        assert payload["object_key"].startswith(f"{upload_service.object_key_prefix}/")
        assert payload["image_url"]
        assert payload["byte_count"] == len(_create_minimal_png())

    def test_non_image_returns_400(self, upload_service):
        client   = TestUploadEndpointErrorHandling._create_test_client(upload_service)
        response = client.post("/api/upload", files = {"file" : ("note.txt", b"hello", "text/plain")})

        assert response.status_code == 400
        assert "이미지 파일만" in response.json()["detail"]

    def test_empty_file_returns_400(self, upload_service):
        client   = TestUploadEndpointErrorHandling._create_test_client(upload_service)
        response = client.post("/api/upload", files = {"file" : ("empty.png", b"", "image/png")})

        assert response.status_code == 400
        assert "빈 파일" in response.json()["detail"]

    def test_oversized_file_returns_413(self, upload_service):
        client        = TestUploadEndpointErrorHandling._create_test_client(upload_service)
        oversize_bytes = b"\x00" * (upload_service.maximum_byte_count + 1)
        response      = client.post("/api/upload",
                                    files = {"file" : ("big.png", oversize_bytes, "image/png")})

        assert response.status_code == 413
        assert "너무 큽니다" in response.json()["detail"]

    def test_missing_file_returns_422(self, upload_service):
        client   = TestUploadEndpointErrorHandling._create_test_client(upload_service)
        response = client.post("/api/upload")

        assert response.status_code == 422   # FastAPI 가 필수 필드 누락을 잡는다


class TestUploadEndpointAuthentication:
    def test_missing_token_is_rejected(self):
        # 업로드는 인증이 필요하다 — 열어두면 누구나 사내 스토리지에 파일을 쌓을 수 있다.
        # server.py 가 실제로 인증을 요구하는지는 살아 있는 서버로만 확인할 수 있으므로,
        # 서버가 떠 있을 때만 검사하고 아니면 skip 한다.
        try:
            request = urllib.request.Request("http://localhost:8000/api/upload", data = b"", method = "POST")
            urllib.request.urlopen(request, timeout = 5)
            pytest.fail("인증 없이 업로드가 허용되었습니다")
        except urllib.error.HTTPError as http_error:
            assert http_error.code in (401, 422), f"기대한 401/422 가 아닙니다 : {http_error.code}"
        except urllib.error.URLError:
            pytest.skip("백엔드(8000)가 실행 중이 아닙니다")


##################################################
# ⑥ Lifecycle : 24시간 자동 만료 규칙이 걸려 있는가
##################################################

@requires_minio
class TestBucketLifecyclePolicy:
    def test_expiry_rule_is_configured(self):
        # mc ilm rule add --expire-days 1 myminio/vision-uploads 로 심는 규칙을 검증한다.
        # 규칙이 없으면 테스트 파일이 로컬 드라이브에 무한정 쌓인다.
        try:
            configuration = s3_helper.s3_client.get_bucket_lifecycle_configuration(
                Bucket = s3_helper.bucket_name)
        except Exception:
            pytest.skip("Lifecycle 규칙이 아직 없습니다 : mc ilm rule add --expire-days 1 myminio/vision-uploads")

        enabled_expiry_day_list = [
            rule["Expiration"]["Days"]
            for rule in configuration.get("Rules", [])
            if rule.get("Status") == "Enabled" and "Days" in rule.get("Expiration", {})]

        assert enabled_expiry_day_list, "활성화된 만료 규칙이 없습니다"
        assert min(enabled_expiry_day_list) <= 1, \
            f"만료 기간이 1일보다 깁니다 : {enabled_expiry_day_list}"

    def test_presigned_expiration_does_not_outlive_object(self, upload_service):
        # 객체가 24시간 뒤 사라지는데 링크 유효기간이 더 길면, 링크는 살아 있고 객체는 없어 404 가 난다
        one_day_second_count = 24 * 60 * 60
        assert upload_service.presigned_expiration_second_count <= one_day_second_count, (
            "IMAGE_PRESIGNED_EXPIRATION_SECOND_COUNT 가 Lifecycle 만료(1일)보다 깁니다. "
            "링크만 살아남아 404 가 발생합니다.")
