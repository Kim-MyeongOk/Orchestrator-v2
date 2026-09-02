파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\common\storage\s3_helper.py`

클래스 기능: `S3Helper` - AWS S3 / MinIO / Cloudflare R2 등 S3 호환 스토리지 공통 헬퍼

> **외부에서 받아온 공통 헬퍼다.** 프로젝트 파이썬 스타일(콜론 정렬·docstring 미사용 등)과 다르지만
> 사내 공용 코드라 원본을 그대로 유지한다. **boto3 를 직접 호출하지 말고 이 모듈의 `s3_helper` 인스턴스를 쓴다.**

싱글톤: 모듈 하단의 `s3_helper = S3Helper()` — 임포트 시점에 환경변수를 읽어 boto3 클라이언트를 만든다

환경변수: `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION_NAME`,
`S3_BUCKET_NAME`, `S3_USE_SSL`, `S3_VERIFY_SSL`, `S3_PUBLIC_DOMAIN`

하위 함수 기능:
- `upload_file(file_path, object_name, extra_args)`: 로컬 파일 → 버킷
- `upload_fileobj(file_obj, object_name, extra_args)`: 메모리 파일 객체 → 버킷 (FastAPI `UploadFile` 용)
- `download_file(object_name, download_path)`: 버킷 → 로컬 파일
- `download_fileobj(object_name)`: 버킷 → `BytesIO` 스트림
- `generate_presigned_url(object_name, expiration)`: 서명된 임시 접근 URL (엔드포인트 기준이라 MinIO 에서도 올바르다)
- `get_public_https_url(object_name)`: 고정 URL.
  ⚠️ **`S3_PUBLIC_DOMAIN` 이 없으면 `https://{버킷}.s3.{리전}.amazonaws.com/...` 를 만든다** —
  MinIO 를 쓸 때는 반드시 `S3_PUBLIC_DOMAIN=http://{엔드포인트}/{버킷}` 을 지정해야 한다
- `delete_file(object_name)` / `list_files(prefix)`: 삭제 · 평탄한 키 목록
- `list_directory(prefix)`: 1단계 계층(folders/files) 분리 조회
- `print_file_tree(prefix, indent)`: 터미널 트리 출력
