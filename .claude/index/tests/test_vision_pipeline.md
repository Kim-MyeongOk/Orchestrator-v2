파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\tests\test_vision_pipeline.py`

모듈 기능: MinIO 업로드 → Presigned 썸네일 → base64 인라인 → `llama3.2-vision` 추론까지의 E2E 통합 테스트 (28 케이스)

실행: `.venv\Scripts\python.exe -m pytest tests/test_vision_pipeline.py -v`

**인프라 의존은 skip 으로 처리한다.** MinIO 나 Ollama 가 없으면 해당 클래스만 건너뛰고 나머지는 그대로 돈다
— 인프라 사정으로 테스트가 "실패"하면 신호가 무뎌지기 때문이다.
- `requires_minio`  : `list_buckets()` 성공 여부
- `requires_vision` : `/api/tags` 에 `llama3.2-vision` 존재 여부

> `.env` 를 `override = True` 로 먼저 올린다. `s3_helper` 가 **임포트 시점에** 환경변수를 읽으므로
> 다른 임포트보다 앞서야 하고, 터미널에 남은 변수가 `.env` 를 이기면 결과가 재현되지 않는다.

테스트 클래스:
- `TestStorageConfiguration` : 버킷명 설정 여부, **목 서버(5599) 오인 방지**, 설정 요약 출력
- `TestImageUploadValidation` : 허용/거부 MIME, `charset` 파라미터 처리, UUID 키 생성, 확장자 매핑
- `TestMinioUploadRoundTrip` : 업로드 → presigned GET(200, `Content-Type`, **바이트 일치**),
  버킷 목록 반영, 삭제 후 404(= Lifecycle 만료 후 상황)
- `TestVisionMessageBuilding` : 텍스트 전용은 문자열 유지, URL 통과, 5장 상한, 빈 값 무시, 미해석 URL 건너뜀
- `TestVisionInlineConversion` : presigned URL → MinIO 재조회 → `data:` URI, **원본 바이트 일치**
- `TestVisionInferenceEndToEnd` : 판별 가능한 이미지(빨강 배경/파랑 원/흰 글자 HELLO)로 실제 추론.
  색·글자 키워드 중 하나라도 언급되면 인식 성공으로 본다 (문장 전체 비교는 쉽게 깨진다).
  텍스트 전용 질문 회귀도 함께 검증
- `TestUploadEndpointErrorHandling` : 200 / 400(형식·빈 파일) / 413(용량) / 422(누락).
  실행 중인 서버에 의존하지 않도록 `server.py` 와 같은 검증 흐름의 앱을 그 자리에서 만든다
- `TestUploadEndpointAuthentication` : 인증 없는 업로드 거부 (서버가 떠 있을 때만 검사, 아니면 skip)
- `TestBucketLifecyclePolicy` : 24시간 만료 규칙 존재, **presigned 유효기간이 만료보다 길지 않은지**

헬퍼:
- `_create_recognizable_png()`: Pillow 로 색·도형·글자가 뚜렷한 이미지 생성 (추론 성공 판정용)
- `_create_minimal_png()`: 1x1 PNG (업로드 경로만 볼 때)
- `uploaded_object_key_list` 픽스처: 테스트가 남긴 객체를 종료 시 반드시 삭제
