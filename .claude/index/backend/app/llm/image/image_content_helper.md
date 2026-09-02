파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\image\image_content_helper.py`

클래스 기능: `ImageContentHelper` - 멀티모달 메시지 본문에서 이미지 블록을 다루는 정적 헬퍼

`VisionMessageBuilder` 가 만든 블록 구조를 되돌려 읽는다.
`[{"type": "text", ...}, {"type": "image_url", ...}]`

> **문구가 중요하다.** 이미지를 걷어내고 "이 모델은 이미지를 지원하지 않는다"고만 쓰면
> 모델이 "저는 이미지를 볼 수 없습니다"로 거절해 버린다 — 비전 모델이 이미 설명해 둔 내용이
> 대화에 있어도 쓰지 않는다. 그래서 설명이 있으면 그 내용을 이미지 자리에 그대로 싣는다.

원본 메시지는 절대 수정하지 않고 `model_copy(update=...)` 로 사본을 만든다 (체크포인트 보존).

하위 함수 기능:
- `_is_image_block(content_block)`: 블록 type 이 image_url/image 인지 판별
- `has_image_block(message_content)`: 메시지 본문에 이미지 블록이 있는지
- `build_replacement_text(description_text)`: 이미지 자리에 넣을 텍스트. 설명이 있으면 그것을 근거로 싣는다
- `strip_image_block(message_content, description_text)`: 이미지 블록 제거 + 대체 문구 삽입.
  남은 것이 텍스트 하나뿐이면 평범한 문자열로 되돌린다 (블록 배열을 남기면 일부 프로바이더가 멀티모달로 오해한다)
- `limit_image_block_list(message_list, image_maximum_count)`: 최신 N장만 남기고 오래된 것부터 제거
- `_find_following_answer_text(message_list, image_message_index)`: 이미지 질문 바로 뒤의 AI 답변을 찾는다 (= 그 이미지의 설명)
- `strip_image_block_list(message_list)`: 목록 전체에서 이미지 제거 (비전 미지원 모델용)

상수: `IMAGE_BLOCK_TYPE_SET` · `REMOVED_IMAGE_NOTICE_TEXT` · `IMAGE_DESCRIPTION_TEMPLATE`
