##################################################
# 북마크 서비스 (답변 단위 · chat_bookmark 테이블)
#
# 북마크 대상은 "방 안에서 몇 번째 답변인가"(agent_index) 로 식별한다.
# memo 는 사용자가 그 답변에 직접 남기는 기록이다.
##################################################

from typing import Any
from typing import Dict
from typing import Optional

from fastapi import HTTPException

from app.database.table_query.chat_bookmark_query import ChatBookmarkQuery
from app.database.table_query.chat_room_query     import ChatRoomQuery
from app.monitor.api.bookmark_memo_update_request import BookmarkMemoUpdateRequest
from app.monitor.api.bookmark_upsert_request      import BookmarkUpsertRequest
from app.monitor.service.auth_service             import AuthService


class BookmarkService:
    MEMO_MAXIMUM_LENGTH    = 1000   # 북마크 메모 최대 길이 (기본값 : 1000)
    PREVIEW_MAXIMUM_LENGTH = 500    # 목록 미리보기 스냅샷 최대 길이

    def __init__(self, checkpoint_connection_pool : Any, auth_service : AuthService) -> None:
        self.checkpoint_connection_pool = checkpoint_connection_pool
        self.auth_service               = auth_service

    @staticmethod
    def normalize_memo(memo : Optional[str]) -> Optional[str]:
        # 메모 정규화 : 앞뒤 공백 제거 후 빈 문자열은 NULL(메모 없음)로, 그 외는 최대 길이로 자른다
        if memo is None:
            return None
        trimmed_memo = memo.strip()
        if not trimmed_memo:
            return None
        return trimmed_memo[:BookmarkService.MEMO_MAXIMUM_LENGTH]

    async def list_bookmarks_async(self, authorization : Optional[str]) -> Dict[str, Any]:
        # 인증된 사용자의 북마크만 최신순으로 반환한다 (스코핑 키는 요청값이 아니라 토큰의 user_id)
        user_id = self.auth_service.require_authenticated_user_id(authorization)
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute(ChatBookmarkQuery.SELECT_LIST_BY_USER, (user_id,))
            bookmark_row_list = await cursor.fetchall()
        return {"bookmarks" : [dict(bookmark_row) for bookmark_row in bookmark_row_list]}

    async def upsert_bookmark_async(self, bookmark_request : BookmarkUpsertRequest,
                                    authorization : Optional[str]) -> Dict[str, Any]:
        # 북마크 추가 : 소유자는 토큰의 user_id 로 강제한다. 남의 방에는 북마크할 수 없다.
        user_id = self.auth_service.require_authenticated_user_id(authorization)
        if bookmark_request.agent_index < 0:
            raise HTTPException(status_code = 400, detail = "INVALID AGENT INDEX")

        completed_at_second = (bookmark_request.completed_at / 1000) if bookmark_request.completed_at else None
        memo_text           = BookmarkService.normalize_memo(bookmark_request.memo)
        async with self.checkpoint_connection_pool.connection() as connection:
            # 방 소유권 확인 : 본인 소유가 아니면(또는 없는 방이면) INSERT 대상 자체가 없다
            cursor = await connection.execute(
                ChatRoomQuery.SELECT_OWNED_ROOM, (bookmark_request.room_id, user_id))
            if await cursor.fetchone() is None:
                raise HTTPException(status_code = 403, detail = "ROOM ACCESS DENIED")
            # 같은 답변을 다시 북마크하면 미리보기 스냅샷만 갱신한다 (중복 행을 만들지 않는다)
            # 메모는 COALESCE 로 보존한다 — 캐시 재등록처럼 메모를 싣지 않은 요청이 기존 메모를 지우면 안 된다
            await connection.execute(
                ChatBookmarkQuery.UPSERT,
                (bookmark_request.bookmark_id, user_id, bookmark_request.room_id, bookmark_request.agent_index,
                 bookmark_request.text[:BookmarkService.PREVIEW_MAXIMUM_LENGTH], completed_at_second, memo_text))
        return {"status" : "ok"}

    async def update_bookmark_memo_async(self, bookmark_id : str, memo_request : BookmarkMemoUpdateRequest,
                                         authorization : Optional[str]) -> Dict[str, Any]:
        # 메모 수정 : 본인 소유 북마크만 수정 가능. 빈 문자열/누락이면 메모를 지운다(NULL).
        user_id   = self.auth_service.require_authenticated_user_id(authorization)
        memo_text = BookmarkService.normalize_memo(memo_request.memo)
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute(
                ChatBookmarkQuery.UPDATE_MEMO_BY_OWNER, (memo_text, bookmark_id, user_id))
            if cursor.rowcount == 0:
                raise HTTPException(status_code = 404, detail = f"BOOKMARK NOT FOUND : {bookmark_id}")
        return {"status" : "ok", "bookmark_id" : bookmark_id, "memo" : memo_text}

    async def delete_bookmark_async(self, bookmark_id : str, authorization : Optional[str]) -> Dict[str, Any]:
        # 본인 소유 북마크만 삭제 가능. 이미 없으면 404 대신 성공으로 처리한다 (토글 연타/낙관적 UI 재시도 대비)
        user_id = self.auth_service.require_authenticated_user_id(authorization)
        async with self.checkpoint_connection_pool.connection() as connection:
            await connection.execute(ChatBookmarkQuery.DELETE_BY_OWNER, (bookmark_id, user_id))
        return {"status" : "deleted"}
