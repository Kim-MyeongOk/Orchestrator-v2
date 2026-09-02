파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\image\vision_message_builder.py`

클래스 기능: `VisionMessageBuilder` - 텍스트 질문 + 이미지 URL 을 OpenAI 멀티모달 content 블록으로 조립

```python
[{"type": "text", "text": ...}, {"type": "image_url", "image_url": {"url": ...}}, ...]
```

**두 가지 전달 방식**

| 모드 | `VISION_IMAGE_INLINE_BASE64` | 동작 | 대상 |
|---|---|---|---|
| URL | `false` (기본) | MinIO URL 을 그대로 넘긴다 — 모델 서버가 직접 내려받는다 | vLLM · OpenAI 규격 |
| 인라인 | `true` | MinIO 에서 내려받아 `data:` URI(base64)로 바꿔 넣는다 | **Ollama** (URL 을 못 읽음) |

> Ollama 가 URL 대신 base64 를 요구한다는 점은 `app/llm/agent/image_attachment_interceptor.py` 주석에도 기록되어 있다.

상수: `IMAGE_MAXIMUM_COUNT`=5 (컨텍스트가 이미지로 뒤덮이는 것을 막는다. 프론트 `IMAGE_ATTACHMENT_MAXIMUM_COUNT` 와 맞춘다)

**이미지가 없으면 문자열을 그대로 돌려준다.** 블록 배열로 감싸면 체크포인트 저장 형태가 달라져
기존 대화 복원 로직이 어긋나기 때문이다. 이미지를 하나도 싣지 못한 경우에도 텍스트 전용으로 되돌린다.

하위 함수 기능:
- `create_from_environment()`: 환경변수로 인스턴스 생성
- `_extract_object_key(image_url)`: URL 경로에서 `{prefix}/{uuid}.{ext}` 조각을 되찾는다
  (presigned 의 서명 쿼리스트링은 버린다). 인라인 모드에서 원본을 다시 읽기 위해 필요
- `_build_image_block(image_url)`: 모드에 맞는 image_url 블록 생성 (실패 시 `None` → 해당 이미지만 건너뜀)
- `build_message_content(message_text, image_url_list)`: 최종 content (문자열 또는 블록 배열)
