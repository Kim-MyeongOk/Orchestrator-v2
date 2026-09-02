파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agentackendpp\monitor\service\image_upload_handler.py`

클래스 기능: `ImageUploadHandler` - `POST /api/upload` 의 HTTP 계층 (검증·상태 코드)

> 실제 저장은 `ImageUploadService` 가 맡는다. 여기서는 상태 코드만 책임진다.
> **400** 형식 오류·빈 파일 / **413** 용량 초과 / **401** 인증 없음 / **502** 스토리지 장애

하위 함수 기능:
- `upload_image_async(file, authorization)`: 인증 → 형식 검증 → 크기 검증 → 업로드 → URL 발급.
  크기는 헤더가 아니라 **실제로 읽은 바이트**로 판단한다 (Content-Length 는 위조될 수 있다).
  boto3 는 동기 라이브러리라 `asyncio.to_thread` 로 뺀다
