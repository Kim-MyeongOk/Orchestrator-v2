import uuid
import base64
import json

from typing   import Optional
from typing   import Tuple
from datetime import datetime
from binascii import Error
from typing   import Dict
from typing   import Any
from fastapi  import APIRouter
from fastapi  import HTTPException
from fastapi  import Header
from fastapi  import Query

from app.llm.chat.chat_query_service import ChatQueryService
from app.llm.api.thread_response     import ThreadListResponse
from app.llm.api.thread_response     import ThreadDetailResponse
from app.llm.api.timeline_response   import TimelineResponse

class ChatAPIRouter:
    def __init__(self, chat_query_service : ChatQueryService) -> None:
        self.chat_query_service = chat_query_service
        self.api_router         = APIRouter(prefix = "/llm", tags = ["llm-chat"])
        self.api_router.add_api_route("/threads"               , self.get_thread_list_async  , methods = ["GET"], response_model = ThreadListResponse  )
        self.api_router.add_api_route("/threads/{thread_id}"   , self.get_thread_detail_async, methods = ["GET"], response_model = ThreadDetailResponse)
        self.api_router.add_api_route("/jobs/{run_id}/timeline", self.get_job_timeline_async , methods = ["GET"], response_model = TimelineResponse    )

    @staticmethod
    def _decode_thread_cursor(cursor : Optional[str]) -> Tuple[Optional[datetime], Optional[uuid.UUID]]:
        if cursor is None:
            return None, None
        try:
            padding_text      = "=" * (-len(cursor) % 4)
            cursor_bytes      = base64.urlsafe_b64decode(f"{cursor}{padding_text}")
            cursor_dictionary = json.loads(cursor_bytes.decode("utf-8"))
            cursor_updated_at = datetime.fromisoformat(cursor_dictionary["updated_at"])
            cursor_thread_id  = uuid.UUID(cursor_dictionary["thread_id"])
            if cursor_updated_at.tzinfo is None:
                raise ValueError("CURSOR TIMEZONE IS REQUIRED : updated_at")
            return cursor_updated_at, cursor_thread_id
        except (Error, ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exception:
            raise HTTPException(status_code = 400, detail = "INVALID CURSOR") from exception

    @staticmethod
    def _encode_thread_cursor(thread_dictionary : Dict[str, Any]) -> str:
        cursor_dictionary = {
            "updated_at" : thread_dictionary["updated_at"],
            "thread_id"  : thread_dictionary["thread_id"]
        }
        cursor_bytes = json.dumps(cursor_dictionary, separators = (",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(cursor_bytes).decode("ascii").rstrip("=")

    def get_router(self) -> APIRouter:
        return self.api_router

    async def get_thread_list_async(self, x_user_id : uuid.UUID = Header(alias = "X-User-Id"), cursor : Optional[str] = Query(default = None), limit : int = Query(default = 20, ge = 1, le = 100)) -> Dict[str, Any]:
        cursor_updated_at, cursor_thread_id = ChatAPIRouter._decode_thread_cursor(cursor)
        thread_dictionary_list = await self.chat_query_service.get_thread_list_async(x_user_id, cursor_updated_at, cursor_thread_id, limit)
        next_cursor = ChatAPIRouter._encode_thread_cursor(thread_dictionary_list[-1]) if len(thread_dictionary_list) == limit else None
        return {"thread_list" : thread_dictionary_list, "next_cursor" : next_cursor}

    async def get_thread_detail_async(self, thread_id : uuid.UUID, x_user_id : uuid.UUID = Header(alias = "X-User-Id"), limit : int = Query(default = 100, ge = 1, le = 500)) -> Dict[str, Any]:
        try:
            return await self.chat_query_service.get_thread_detail_async(thread_id, x_user_id, limit)
        except ValueError as value_error:
            raise HTTPException(status_code = 404, detail = str(value_error)) from value_error

    async def get_job_timeline_async(self, run_id : uuid.UUID, x_user_id : uuid.UUID = Header(alias = "X-User-Id"), after_seq : int = Query(default = 0, ge = 0), limit : int = Query(default = 500, ge = 1, le = 1000)) -> Dict[str, Any]:
        try:
            return await self.chat_query_service.get_job_timeline_async(run_id, x_user_id, after_seq, limit)
        except ValueError as value_error:
            raise HTTPException(status_code = 404, detail = str(value_error)) from value_error
