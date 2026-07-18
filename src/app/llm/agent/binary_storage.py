##################################################
# 바이너리 스토리지 추상화 (이미지 격리용)
# State 에서 추출한 대용량 바이너리를 외부 스토리지에 격리 저장한다.
# BinaryStorageProtocol 만 만족하면 구현체 교체가 가능하다 (로컬 파일 → S3 등).
#
#   save_binary_async(binary_data)  -> reference_id (State 에는 이 참조값만 남는다)
#   load_binary_async(reference_id) -> bytes        (모델 호출 직전 재주입 시 사용)
##################################################

import os
import re
import uuid
import asyncio

from typing import Protocol


class BinaryStorageProtocol(Protocol):
    async def save_binary_async(self, binary_data : bytes) -> str: ...
    async def load_binary_async(self, reference_id : str) -> bytes: ...


class LocalFileBinaryStorage:
    # 로컬 파일 시스템 구현체. S3 전환 시 같은 프로토콜의 S3BinaryStorage 를 만들어 주입만 바꾸면 된다.
    REFERENCE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

    def __init__(self, storage_directory_path : str) -> None:
        self.storage_directory_path = storage_directory_path
        os.makedirs(storage_directory_path, exist_ok = True)

    def _create_file_path(self, reference_id : str) -> str:
        # 경로 조작 방지 : reference_id 는 uuid4 hex 형식만 허용한다
        if not LocalFileBinaryStorage.REFERENCE_ID_PATTERN.match(reference_id):
            raise ValueError(f"INVALID BINARY REFERENCE ID : {reference_id}")
        return os.path.join(self.storage_directory_path, f"{reference_id}.bin")

    async def save_binary_async(self, binary_data : bytes) -> str:
        reference_id = uuid.uuid4().hex
        file_path    = self._create_file_path(reference_id)
        await asyncio.to_thread(LocalFileBinaryStorage._write_file, file_path, binary_data)
        return reference_id

    async def load_binary_async(self, reference_id : str) -> bytes:
        file_path = self._create_file_path(reference_id)
        return await asyncio.to_thread(LocalFileBinaryStorage._read_file, file_path)

    @staticmethod
    def _write_file(file_path : str, binary_data : bytes) -> None:
        with open(file_path, "wb") as binary_file:
            binary_file.write(binary_data)

    @staticmethod
    def _read_file(file_path : str) -> bytes:
        with open(file_path, "rb") as binary_file:
            return binary_file.read()
