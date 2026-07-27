import os
import io
import logging
from typing import Optional, List, Dict, Any
import boto3
from botocore.exceptions import ClientError

# 로거 설정
logger = logging.getLogger(__name__)


class S3Helper:
    """
    AWS S3, Cloudflare R2, MinIO 등 S3 호환 스토리지를 제어하는 공통 헬퍼 클래스
    (HTTPS 통신, 업로드, 다운로드, Presigned URL 생성, 삭제, 계층형 파일 트리 출력 기능 제공)
    """

    def __init__(self):
        # 환경변수에서 설정값 로드
        self.endpoint_url = os.getenv("S3_ENDPOINT_URL")  # MinIO/R2 커스텀 엔드포인트 (예: https://localhost:9000)
        self.access_key = os.getenv("S3_ACCESS_KEY_ID")
        self.secret_key = os.getenv("S3_SECRET_ACCESS_KEY")
        self.region_name = os.getenv("S3_REGION_NAME", "ap-northeast-2")
        self.bucket_name = os.getenv("S3_BUCKET_NAME")

        # HTTPS 사용 여부 (기본값 True, 'false' 문자열일 때만 False 처리)
        use_ssl_env = os.getenv("S3_USE_SSL", "true").lower()
        self.use_ssl = use_ssl_env not in ("false", "0", "no")

        # Boto3 S3 Client 기본 옵션 설정 (HTTPS 적용)
        client_kwargs = {
            "service_name": "s3",
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
            "region_name": self.region_name,
            "use_ssl": self.use_ssl,
        }

        # 커스텀 엔드포인트(MinIO / Cloudflare R2 등) 지정 시 처리
        if self.endpoint_url:
            # http://로 잘못 들어온 주소에 SSL을 강제하는 경우 https://로 보정
            if self.use_ssl and self.endpoint_url.startswith("http://"):
                self.endpoint_url = self.endpoint_url.replace("http://", "https://", 1)
            client_kwargs["endpoint_url"] = self.endpoint_url

        # 로컬 테스트용 자체 서명 SSL 증명서 허용 옵션 (S3_VERIFY_SSL=false 설정 시)
        verify_env = os.getenv("S3_VERIFY_SSL", "true").lower()
        if verify_env in ("false", "0", "no"):
            client_kwargs["verify"] = False

        self.s3_client = boto3.client(**client_kwargs)

    # ==================== [ 업로드 기능 ] ====================

    def upload_file(self, file_path: str, object_name: Optional[str] = None, extra_args: Optional[dict] = None) -> bool:
        """
        로컬 파일 -> S3 버킷 업로드
        :param file_path: 업로드할 로컬 파일 경로
        :param object_name: S3 내 저장될 파일 경로/명 (지정 안 할 경우 로컬 파일명 사용)
        :param extra_args: ContentType 등 추가 메타데이터 (예: {'ContentType': 'image/png'})
        """
        if object_name is None:
            object_name = os.path.basename(file_path)

        try:
            self.s3_client.upload_file(file_path, self.bucket_name, object_name, ExtraArgs=extra_args)
            logger.info(f"S3 파일 업로드 성공: {object_name}")
            return True
        except ClientError as e:
            logger.error(f"S3 파일 업로드 실패: {e}")
            return False

    def upload_fileobj(self, file_obj: Any, object_name: str, extra_args: Optional[dict] = None) -> bool:
        """
        메모리상의 파일 객체(FastAPI UploadFile.file 등) -> S3 업로드
        """
        try:
            self.s3_client.upload_fileobj(file_obj, self.bucket_name, object_name, ExtraArgs=extra_args)
            logger.info(f"S3 객체 업로드 성공: {object_name}")
            return True
        except ClientError as e:
            logger.error(f"S3 객체 업로드 실패: {e}")
            return False

    # ==================== [ 다운로드 기능 ] ====================

    def download_file(self, object_name: str, download_path: str) -> bool:
        """
        S3 파일 -> 로컬 디렉토리 파일로 다운로드
        :param object_name: S3 내 파일 경로/명
        :param download_path: 저장할 로컬 파일 경로
        """
        try:
            dir_name = os.path.dirname(download_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)

            self.s3_client.download_file(self.bucket_name, object_name, download_path)
            logger.info(f"S3 파일 다운로드 성공: {object_name} -> {download_path}")
            return True
        except ClientError as e:
            logger.error(f"S3 파일 다운로드 실패: {e}")
            return False

    def download_fileobj(self, object_name: str) -> Optional[io.BytesIO]:
        """
        S3 파일 -> 메모리(BytesIO) 스트림으로 다운로드
        """
        try:
            file_stream = io.BytesIO()
            self.s3_client.download_fileobj(self.bucket_name, object_name, file_stream)
            file_stream.seek(0)
            logger.info(f"S3 메모리 스트림 다운로드 성공: {object_name}")
            return file_stream
        except ClientError as e:
            logger.error(f"S3 메모리 스트림 다운로드 실패: {e}")
            return None

    # ==================== [ HTTPS URL 생성 ] ====================

    def generate_presigned_url(self, object_name: str, expiration: int = 3600) -> Optional[str]:
        """
        보안 임시 접근용 HTTPS Presigned URL 생성
        :param expiration: 유효 기간 (초 단위, 기본 3600초 = 1시간)
        """
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_name},
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logger.error(f"HTTPS Presigned URL 생성 실패: {e}")
            return None

    def get_public_https_url(self, object_name: str) -> str:
        """
        퍼블릭 읽기 허용 버킷 또는 CDN 연동 시 사용할 고정 HTTPS URL 반환
        """
        public_domain = os.getenv("S3_PUBLIC_DOMAIN")
        if public_domain:
            if not public_domain.startswith("http"):
                public_domain = f"https://{public_domain}"
            return f"{public_domain.rstrip('/')}/{object_name.lstrip('/')}"

        return f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{object_name.lstrip('/')}"

    # ==================== [ 삭제 및 조회 ] ====================

    def delete_file(self, object_name: str) -> bool:
        """S3 파일 삭제"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)
            logger.info(f"S3 파일 삭제 성공: {object_name}")
            return True
        except ClientError as e:
            logger.error(f"S3 파일 삭제 실패: {e}")
            return False

    def list_files(self, prefix: str = "") -> List[str]:
        """버킷 내 모든 파일 키(Key) 목록 조회 (평탄한 목록)"""
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            if 'Contents' in response:
                return [item['Key'] for item in response['Contents']]
            return []
        except ClientError as e:
            logger.error(f"S3 파일 목록 조회 실패: {e}")
            return []

    # ==================== [ 파일 트리 & 디렉토리 탐색 ] ====================

    def list_directory(self, prefix: str = "") -> Dict[str, Any]:
        """
        특정 경로 하위의 폴더 목록(folders)과 파일 목록(files)을 1단계 계층으로 분리하여 조회
        """
        if prefix and not prefix.endswith('/'):
            prefix += '/'

        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                Delimiter='/'
            )

            # 하위 폴더 목록 추출
            folders = [p['Prefix'] for p in response.get('CommonPrefixes', [])]

            # 현재 위치의 파일 목록 추출 (폴더 본인 키 제외)
            files = []
            for item in response.get('Contents', []):
                if item['Key'] != prefix:
                    files.append({
                        'key': item['Key'],
                        'name': item['Key'].replace(prefix, '', 1),
                        'size': item['Size'],
                        'last_modified': item['LastModified'].isoformat()
                    })

            return {
                'prefix': prefix,
                'folders': folders,
                'files': files
            }
        except ClientError as e:
            logger.error(f"S3 디렉토리 조회 실패: {e}")
            return {'prefix': prefix, 'folders': [], 'files': []}

    def print_file_tree(self, prefix: str = "", indent: str = "") -> None:
        """
        S3 버킷 내의 파일/폴더 구조를 터미널에 트리 형태(tree 명령 스타일)로 출력
        :param prefix: 출력할 시작 폴더 경로 (기본값 ""는 전체 버킷)
        :param indent: 재귀 호출용 들여쓰기 내부 파라미터
        """
        if indent == "":
            root_name = prefix.rstrip('/') if prefix else self.bucket_name
            print(f"📁 [{root_name}]")

        dir_info = self.list_directory(prefix)
        folders = dir_info['folders']
        files = dir_info['files']

        total_items = len(folders) + len(files)
        current_count = 0

        # 1. 하위 폴더 트리 출력
        for folder_prefix in folders:
            current_count += 1
            is_last = (current_count == total_items)
            branch = "└── " if is_last else "├── "
            folder_name = folder_prefix.rstrip('/').split('/')[-1]

            print(f"{indent}{branch}📁 {folder_name}/")

            next_indent = indent + ("    " if is_last else "│   ")
            self.print_file_tree(prefix=folder_prefix, indent=next_indent)

        # 2. 파일 목록 트리 출력
        for file in files:
            current_count += 1
            is_last = (current_count == total_items)
            branch = "└── " if is_last else "├── "

            # 파일 크기 가독성 있게 표기 (B, KB, MB)
            size_bytes = file['size']
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

            print(f"{indent}{branch}📄 {file['name']} ({size_str})")


# 싱글톤 인스턴스 생성
s3_helper = S3Helper()