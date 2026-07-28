##################################################
# 채팅방 서비스 (chat_room 테이블)
#
# 스코핑 키는 항상 "토큰에서 꺼낸 user_id" 다. 요청 본문의 user_id 는 신뢰하지 않는다 —
# 그대로 믿으면 남의 방(room_id)을 가로챌 수 있다.
##################################################

from typing import Any
from typing import Dict
from typing import Optional

from fastapi import HTTPException

from app.database.table_query.chat_room_query import ChatRoomQuery
from app.monitor.api.room_upsert_request      import RoomUpsertRequest
from app.monitor.service.auth_service         import AuthService


class RoomService:
    def __init__(self, checkpoint_connection_pool : Any, auth_service : AuthService) -> None:
        self.checkpoint_connection_pool = checkpoint_connection_pool
        self.auth_service               = auth_service

    async def list_rooms_async(self, authorization : Optional[str]) -> Dict[str, Any]:
        # 인증된 사용자의 방 목록만 반환한다 (스코핑 키는 요청값이 아니라 토큰의 user_id)
        user_id = self.auth_service.require_authenticated_user_id(authorization)
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute(ChatRoomQuery.SELECT_LIST_BY_USER, (user_id,))
            room_row_list = await cursor.fetchall()
        return {"rooms" : [dict(room_row) for room_row in room_row_list]}

    async def upsert_room_async(self, room_request : RoomUpsertRequest, authorization : Optional[str]) -> Dict[str, Any]:
        # 방 생성/갱신 : 소유자는 토큰의 user_id 로 강제한다 (요청 본문의 user_id 는 무시). 남의 방(room_id) 갈취 방지
        user_id = self.auth_service.require_authenticated_user_id(authorization)
        await self.auth_service.assert_thread_accessible_async(user_id, room_request.thread_id)
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute(
                ChatRoomQuery.UPSERT,
                (room_request.room_id, user_id, room_request.thread_id, room_request.title,
                 room_request.model, room_request.reasoning_effort))
            if cursor.rowcount == 0:
                raise HTTPException(status_code = 403, detail = "ROOM ACCESS DENIED")
        return {"status" : "ok"}

    async def delete_room_async(self, room_id : str, authorization : Optional[str]) -> Dict[str, Any]:
        # 목록에서만 제거한다 (체크포인트 대화 원본은 retention 배치가 유휴 기준으로 정리). 본인 소유 방만 삭제 가능
        user_id = self.auth_service.require_authenticated_user_id(authorization)
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute(ChatRoomQuery.DELETE_BY_OWNER, (room_id, user_id))
            if cursor.rowcount == 0:
                raise HTTPException(status_code = 404, detail = f"ROOM NOT FOUND : {room_id}")
        return {"status" : "deleted"}
