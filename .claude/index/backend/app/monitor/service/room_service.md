파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agentackendpp\monitor\serviceoom_service.py`

클래스 기능: `RoomService` - 채팅방(`chat_room` 테이블) 목록/생성/갱신/삭제

> 스코핑 키는 항상 **토큰에서 꺼낸 user_id** 다. 요청 본문의 user_id 는 신뢰하지 않는다 —
> 그대로 믿으면 남의 방(room_id)을 가로챌 수 있다.

하위 함수 기능:
- `list_rooms_async(authorization)`: 인증 사용자의 방 목록 (최근 수정순)
- `upsert_room_async(room_request, authorization)`: 생성/갱신. 남의 방이면 403
- `delete_room_async(room_id, authorization)`: 목록에서만 제거 (대화 원본은 retention 배치가 정리). 없으면 404
