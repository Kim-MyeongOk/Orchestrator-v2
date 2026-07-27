##################################################
# 이미지 업로드 서비스 (MinIO / S3 호환)
# 업로드된 이미지를 공통 헬퍼(common.storage.s3_helper.s3_helper)로 버킷에 올리고,
# Vision 모델이 읽을 수 있는 접근 URL 을 돌려준다. boto3 는 직접 호출하지 않는다.
#
# [버킷 자동 생성]
#   버킷이 없으면 최초 업로드 시 만든다. 사내 정책상 생성 권한이 없으면 아래 명령으로 미리 만들어 둔다.
#     mc alias set myminio http://s3.samsung.com:9000 admin password123
#     mc mb myminio/vision-uploads
#
# [24시간 후 자동 삭제 (Lifecycle)]
#   업로드된 이미지가 무한정 쌓이지 않도록 MinIO CLI 로 만료 규칙을 걸어 둔다.
#     mc alias set myminio http://s3.samsung.com:9000 admin password123
#     mc ilm add --expiry-days 1 myminio/vision-uploads
#
#   주의 : 만료 기간(1일)보다 presigned URL 유효기간을 길게 잡으면, 링크는 살아 있는데
#          객체가 사라져 404 가 난다. IMAGE_PRESIGNED_EXPIRATION_SECOND_COUNT 를 24시간 이하로 둔다.
##################################################

import os
import uuid

from typing import Any
from typing import Dict
from typing import Optional

from common.storage.s3_helper import s3_helper


class ImageUploadService:
    # 실제로 브라우저·모델이 렌더링할 수 있는 형식만 받는다 (svg 는 스크립트를 품을 수 있어 제외)
    ALLOWED_CONTENT_TYPE_TO_EXTENSION = {
        "image/png"  : "png",
        "image/jpeg" : "jpg",
        "image/jpg"  : "jpg",
        "image/webp" : "webp",
        "image/gif"  : "gif"
    }
    DEFAULT_EXTENSION = "png"

    def __init__(self,
                 object_key_prefix              : str = "uploads",
                 maximum_byte_count             : int = 10 * 1024 * 1024,
                 url_mode                       : str = "presigned",
                 presigned_expiration_second_count : int = 86400) -> None:
        self.object_key_prefix                 = object_key_prefix.strip("/")
        self.maximum_byte_count                = maximum_byte_count
        self.url_mode                          = url_mode
        self.presigned_expiration_second_count = presigned_expiration_second_count
        self.is_bucket_ready                   = False   # 버킷 확인은 최초 업로드 때 한 번만 한다

    @staticmethod
    def create_from_environment() -> "ImageUploadService":
        return ImageUploadService(
            object_key_prefix                 = os.getenv("IMAGE_UPLOAD_PREFIX", "uploads"),
            maximum_byte_count                = int(os.getenv("IMAGE_UPLOAD_MAXIMUM_BYTE_COUNT", str(10 * 1024 * 1024))),
            url_mode                          = os.getenv("IMAGE_URL_MODE", "presigned").strip().lower(),
            presigned_expiration_second_count = int(os.getenv("IMAGE_PRESIGNED_EXPIRATION_SECOND_COUNT", "86400")))

    def build_object_key(self, content_type : Optional[str]) -> str:
        # 파일명 충돌을 막기 위해 원본 이름을 버리고 UUID 로 새로 짓는다.
        # 원본 이름을 쓰면 경로 조작(../)·한글 깨짐·덮어쓰기가 한꺼번에 따라온다.
        extension = ImageUploadService.ALLOWED_CONTENT_TYPE_TO_EXTENSION.get(
            (content_type or "").split(";")[0].strip().lower(), ImageUploadService.DEFAULT_EXTENSION)
        return f"{self.object_key_prefix}/{uuid.uuid4().hex}.{extension}"

    def is_allowed_content_type(self, content_type : Optional[str]) -> bool:
        return (content_type or "").split(";")[0].strip().lower() in ImageUploadService.ALLOWED_CONTENT_TYPE_TO_EXTENSION

    def describe_storage_configuration(self) -> str:
        # 기동 로그에 한 줄로 남긴다.
        # load_dotenv() 는 이미 설정된 환경변수를 덮어쓰지 않으므로, 터미널에 남은 S3_ENDPOINT_URL 이
        # .env 를 이기고 엉뚱한 스토리지(목 서버 등)를 바라보는 사고가 생긴다. 그게 눈에 보이지 않는 것이 문제였다.
        return (f"S3 STORAGE : endpoint={s3_helper.endpoint_url or '(aws default)'} "
                f"bucket={s3_helper.bucket_name} use_ssl={s3_helper.use_ssl} "
                f"url_mode={self.url_mode} prefix={self.object_key_prefix}")

    @staticmethod
    def assert_storage_configured() -> None:
        # S3_BUCKET_NAME 이 비어 있으면 boto3 안쪽에서 TypeError 로 터져 원인을 알아보기 어렵다.
        # (s3_helper 는 임포트 시점에 환경변수를 읽으므로 .env 로드 순서가 어긋나면 실제로 이 상태가 된다)
        if not s3_helper.bucket_name:
            raise RuntimeError("S3 BUCKET NAME NOT CONFIGURED : CHECK S3_BUCKET_NAME IN .env")

    def ensure_bucket_exists(self) -> None:
        # 버킷이 없으면 만든다. 이미 있거나 생성 권한이 없으면 조용히 넘어가고, 실패는 업로드 단계에서 드러난다.
        if self.is_bucket_ready:
            return
        try:
            s3_helper.s3_client.head_bucket(Bucket = s3_helper.bucket_name)
            self.is_bucket_ready = True
            return
        except Exception:
            pass
        try:
            s3_helper.s3_client.create_bucket(Bucket = s3_helper.bucket_name)
            print(f"S3 BUCKET CREATED : {s3_helper.bucket_name}", flush = True)
            self.is_bucket_ready = True
        except Exception as exception:
            # 권한이 없으면 여기서 막지 않는다 — 관리자가 mc mb 로 만들어 두는 운영도 있다
            print(f"S3 BUCKET NOT READY : {s3_helper.bucket_name} - {exception}", flush = True)

    def build_image_url(self, object_key : str) -> Optional[str]:
        # public  : 버킷을 공개 읽기로 열어둔 경우의 고정 URL (S3_PUBLIC_DOMAIN 필요 — 없으면 AWS 주소가 나온다)
        # presigned : 서명이 붙은 임시 URL. 버킷을 비공개로 두고도 접근할 수 있어 기본값으로 쓴다.
        if self.url_mode == "public":
            return s3_helper.get_public_https_url(object_key)
        return s3_helper.generate_presigned_url(object_key, expiration = self.presigned_expiration_second_count)

    def upload_image(self, file_object : Any, object_key : str, content_type : Optional[str]) -> bool:
        # ContentType 을 실어야 브라우저가 내려받지 않고 그대로 렌더링한다 (없으면 octet-stream 으로 저장된다)
        ImageUploadService.assert_storage_configured()
        self.ensure_bucket_exists()
        extra_argument_dictionary : Dict[str, Any] = {}
        if content_type:
            extra_argument_dictionary["ContentType"] = content_type
        return s3_helper.upload_fileobj(file_object, object_key, extra_args = extra_argument_dictionary or None)
