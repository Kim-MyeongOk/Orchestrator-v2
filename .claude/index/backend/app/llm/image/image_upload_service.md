파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\image\image_upload_service.py`

클래스 기능: `ImageUploadService` - 업로드 이미지를 MinIO(S3 호환)에 저장하고 Vision 모델이 읽을 URL 을 발급

> boto3 를 직접 부르지 않고 `common.storage.s3_helper.s3_helper` 싱글톤을 통해서만 접근한다.

환경변수 (`create_from_environment()`):
| 변수 | 기본값 | 설명 |
|---|---|---|
| `IMAGE_UPLOAD_PREFIX` | `uploads` | 객체 키 접두사 |
| `IMAGE_UPLOAD_MAXIMUM_BYTE_COUNT` | `10485760` (10MB) | 업로드 상한 |
| `IMAGE_URL_MODE` | `presigned` | `presigned`(서명 임시 URL) \| `public`(고정 URL, 버킷 공개 필요) |
| `IMAGE_PRESIGNED_EXPIRATION_SECOND_COUNT` | `86400` (24시간) | presigned 유효기간 |

허용 형식: png / jpeg / webp / gif (**svg 는 스크립트를 품을 수 있어 제외**)

**Lifecycle (24시간 자동 삭제)** — 파일 상단 주석에 `mc` 명령을 적어 두었다.
```bash
mc alias set myminio http://s3.samsung.com:9000 admin password123
mc ilm add --expiry-days 1 myminio/vision-uploads
```
> 만료 기간(1일)보다 presigned 유효기간을 길게 잡으면 링크는 살아 있는데 객체가 사라져 404 가 난다.

하위 함수 기능:
- `create_from_environment()`: 환경변수로 인스턴스 생성
- `build_object_key(content_type)`: `{prefix}/{uuid4hex}.{ext}` 생성.
  원본 파일명을 버리는 이유 — 경로 조작(`../`)·한글 깨짐·덮어쓰기를 한 번에 막는다
- `is_allowed_content_type(content_type)`: 허용 MIME 판별
- `ensure_bucket_exists()`: 버킷 없으면 생성 (최초 1회만 확인, 권한 없으면 경고만 남기고 통과)
- `build_image_url(object_key)`: `url_mode` 에 따라 presigned / public URL 발급
- `upload_image(file_object, object_key, content_type)`: `ContentType` 을 실어 업로드
  (없으면 octet-stream 으로 저장돼 브라우저가 렌더링 대신 다운로드한다)
