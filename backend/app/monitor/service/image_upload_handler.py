##################################################
# 이미지 업로드 라우트 핸들러 (POST /api/upload)
#
# 실제 저장은 ImageUploadService 가 맡고, 여기서는 HTTP 계층의 검증과 상태 코드를 담당한다.
#   400 : 형식 오류 · 빈 파일
#   413 : 용량 초과
#   401 : 인증 없음 (AuthService)
#   502 : 스토리지 장애
##################################################

import asyncio
import io

from typing import Any
from typing import Dict
from typing import Optional

from fastapi import HTTPException
from fastapi import UploadFile

from app.llm.image.image_upload_service import ImageUploadService
from app.monitor.service.auth_service   import AuthService


class ImageUploadHandler:
    def __init__(self, image_upload_service : ImageUploadService, auth_service : AuthService) -> None:
        self.image_upload_service = image_upload_service
        self.auth_service         = auth_service

    async def upload_image_async(self, file : UploadFile, authorization : Optional[str]) -> Dict[str, Any]:
        # 인증을 요구하는 이유 : 열어두면 누구나 사내 스토리지에 파일을 쌓을 수 있다.
        self.auth_service.require_authenticated_user_id(authorization)

        if not self.image_upload_service.is_allowed_content_type(file.content_type):
            raise HTTPException(status_code = 400, detail = "이미지 파일만 업로드할 수 있습니다. (png / jpeg / webp / gif)")

        # 크기 검사는 파일을 통째로 읽어서 한다. UploadFile 은 스풀링되어 큰 파일은 디스크로 넘어가므로
        # 메모리를 잡아먹지 않고, 헤더의 Content-Length 는 위조될 수 있어 믿지 않는다.
        file_bytes = await file.read()
        if len(file_bytes) == 0:
            raise HTTPException(status_code = 400, detail = "빈 파일입니다.")
        if len(file_bytes) > self.image_upload_service.maximum_byte_count:
            maximum_megabyte = self.image_upload_service.maximum_byte_count / (1024 * 1024)
            raise HTTPException(status_code = 413, detail = f"이미지가 너무 큽니다. (최대 {maximum_megabyte:.0f}MB)")

        object_key  = self.image_upload_service.build_object_key(file.content_type)
        # boto3 는 동기 라이브러리라 이벤트 루프를 막지 않도록 스레드로 뺀다
        is_uploaded = await asyncio.to_thread(
            self.image_upload_service.upload_image, io.BytesIO(file_bytes), object_key, file.content_type)
        if not is_uploaded:
            raise HTTPException(status_code = 502, detail = "이미지 저장소에 업로드하지 못했습니다. 스토리지 상태를 확인해주세요.")

        image_url = await asyncio.to_thread(self.image_upload_service.build_image_url, object_key)
        if not image_url:
            raise HTTPException(status_code = 502, detail = "이미지 접근 URL 을 만들지 못했습니다.")
        return {"object_key"   : object_key,
                "image_url"    : image_url,
                "content_type" : file.content_type,
                "byte_count"   : len(file_bytes)}
