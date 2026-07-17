import uuid
import base64
import json
import asyncio

from fastapi           import APIRouter
from typing            import Optional
from typing            import Tuple
from datetime          import datetime
from binascii          import Error
from fastapi           import HTTPException
from typing            import Dict
from typing            import Any
from fastapi           import Request
from typing            import AsyncIterator
from fastapi           import Header
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse
from fastapi           import Query

from app.llm.job.job_manager.job_manager           import JobManager
from app.llm.job.job_subscription.job_subscription import JobSubscription
from common.network.sse.sse_helper                 import SseHelper
from app.llm.api.chat_request                      import ChatRequest
from app.llm.job.job_manager.job_type              import JobType
from app.llm.job.job_manager.job_ownership_error   import JobOwnershipError
from app.llm.api.job_submit_request                import JobSubmitRequest
from app.llm.job.job_manager.job_duplicate_error   import JobDuplicateError
from app.llm.job.job_manager.job_not_found_error   import JobNotFoundError
from app.llm.job.job_manager.job_state_error       import JobStateError
from app.llm.job.job_manager.job_status            import JobStatus

class LLMAPIRouter:
    def __init__(self, job_manager : JobManager, job_subscription : JobSubscription) -> None:
        self.job_manager      = job_manager
        self.job_subscription = job_subscription
        self.api_router       = APIRouter(prefix = "/llm", tags = ["llm"])
        self.api_router.add_api_route("/chat"                , self.chat_async        , methods = ["POST"])
        self.api_router.add_api_route("/jobs"                , self.submit_job_async  , methods = ["POST"], status_code = 202)
        self.api_router.add_api_route("/jobs/{run_id}/stream", self.stream_job_async  , methods = ["GET"])
        self.api_router.add_api_route("/jobs/{run_id}"       , self.get_job_async     , methods = ["GET"])
        self.api_router.add_api_route("/jobs/{run_id}"       , self.cancel_job_async  , methods = ["DELETE"])
        self.api_router.add_api_route("/jobs"                , self.get_job_list_async, methods = ["GET"])

    @staticmethod
    def _decode_cursor(cursor : Optional[str]) -> Tuple[Optional[datetime], Optional[uuid.UUID]]:
        if cursor is None:
            return None, None
        try:
            padding_text      = "=" * (-len(cursor) % 4)
            cursor_bytes      = base64.urlsafe_b64decode(f"{cursor}{padding_text}")
            cursor_dictionary = json.loads(cursor_bytes.decode("utf-8"))
            cursor_created_at = datetime.fromisoformat(cursor_dictionary["created_at"])
            cursor_run_id     = uuid.UUID(cursor_dictionary["run_id"])
            if cursor_created_at.tzinfo is None:
                raise ValueError("CURSOR TIMEZONE IS REQUIRED : created_at")
            return cursor_created_at, cursor_run_id
        except (Error, ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exception:
            raise HTTPException(status_code = 400, detail = "INVALID CURSOR") from exception

    @staticmethod
    def _encode_cursor(job_dictionary : Dict[str, Any]) -> str:
        cursor_dictionary = {
            "created_at" : job_dictionary["created_at"],
            "run_id"     : job_dictionary["run_id"]
        }
        cursor_bytes = json.dumps(cursor_dictionary, separators = (",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(cursor_bytes).decode("ascii").rstrip("=")

    @staticmethod
    def _parse_last_event_sequence_number(last_event_id : Optional[str]) -> Tuple[int, bool]:
        last_event_sequence_number = SseHelper.parse_last_event_id(last_event_id)
        if last_event_id is not None and last_event_sequence_number is None:
            raise HTTPException(status_code = 400, detail = "INVALID LAST-EVENT-ID")
        if last_event_sequence_number is not None and last_event_sequence_number < 0:
            raise HTTPException(status_code = 400, detail = "INVALID LAST-EVENT-ID")
        return last_event_sequence_number or 0, last_event_id is not None

    async def _stream_sync_job_async(self, request : Request, run_id : uuid.UUID, user_id : uuid.UUID, output_format : str) -> AsyncIterator[str]:
        is_finished = False
        try:
            async for sse_text in self.job_subscription.subscribe_async(run_id, 0, output_format, False):
                if await request.is_disconnected():
                    await asyncio.shield(self.job_manager.fail_client_disconnected_async(run_id, user_id))
                    return
                yield sse_text
            is_finished = True
        except asyncio.CancelledError:
            if not is_finished:
                await asyncio.shield(self.job_manager.fail_client_disconnected_async(run_id, user_id))
            raise

    def get_router(self) -> APIRouter:
        return self.api_router

    async def chat_async(self, chat_request : ChatRequest, request : Request, x_user_id : uuid.UUID = Header(alias = "X-User-Id")) -> StreamingResponse:
        try:
            job_dictionary = await self.job_manager.submit_async(
                x_user_id,
                JobType.SYNC,
                chat_request.thread_id,
                [message_request.model_dump(exclude_none = True) for message_request in chat_request.messages],
                chat_request.output_format,
                chat_request.model.model_dump(exclude_none = True) if chat_request.model is not None else None
            )
        except JobOwnershipError as job_ownership_error:
            raise HTTPException(status_code = 403, detail = str(job_ownership_error)) from job_ownership_error
        except ValueError as value_error:
            raise HTTPException(status_code = 400, detail = str(value_error)) from value_error
        run_id = uuid.UUID(job_dictionary["run_id"])
        return StreamingResponse(
            self._stream_sync_job_async(request, run_id, x_user_id, chat_request.output_format),
            media_type = "text/event-stream",
            headers = {
                "Cache-Control"     : "no-cache",
                "X-Accel-Buffering" : "no",
                "X-Run-Id"          : job_dictionary["run_id"],
                "X-Thread-Id"       : job_dictionary["thread_id"]
            }
        )

    async def submit_job_async(self, job_submit_request : JobSubmitRequest, x_user_id : uuid.UUID = Header(alias = "X-User-Id")) -> JSONResponse:
        try:
            job_dictionary = await self.job_manager.submit_async(
                x_user_id,
                JobType.ASYNC,
                job_submit_request.thread_id,
                [message_request.model_dump(exclude_none = True) for message_request in job_submit_request.messages],
                job_submit_request.output_format,
                job_submit_request.model.model_dump(exclude_none = True) if job_submit_request.model is not None else None,
                job_submit_request.idempotency_key
            )
        except JobDuplicateError as job_duplicate_error:
            raise HTTPException(
                status_code = 409,
                detail = {"message" : str(job_duplicate_error), "run_id" : job_duplicate_error.existing_run_id}
            ) from job_duplicate_error
        except JobOwnershipError as job_ownership_error:
            raise HTTPException(status_code = 403, detail = str(job_ownership_error)) from job_ownership_error
        except ValueError as value_error:
            raise HTTPException(status_code = 400, detail = str(value_error)) from value_error
        return JSONResponse(status_code = 202, content = job_dictionary)

    async def stream_job_async(self, run_id : uuid.UUID, x_user_id : uuid.UUID = Header(alias = "X-User-Id"), output_format : Optional[str] = Query(default = None, alias = "format"), include_events : bool = Query(default = False), last_event_id : Optional[str] = Header(default = None, alias = "Last-Event-ID")) -> StreamingResponse:
        try:
            job_dictionary = await self.job_manager.get_persisted_job_async(run_id, x_user_id)
        except JobNotFoundError as job_not_found_error:
            raise HTTPException(status_code = 404, detail = str(job_not_found_error)) from job_not_found_error
        actual_output_format = output_format or job_dictionary["output_format"]
        if actual_output_format not in {"deepagents", "openai"}:
            raise HTTPException(status_code = 400, detail = "INVALID OUTPUT FORMAT")
        last_event_sequence_number, is_resume = LLMAPIRouter._parse_last_event_sequence_number(last_event_id)
        return StreamingResponse(
            self.job_subscription.subscribe_async(run_id, last_event_sequence_number, actual_output_format, include_events, is_resume),
            media_type = "text/event-stream",
            headers = {
                "Cache-Control"     : "no-cache",
                "X-Accel-Buffering" : "no"
            }
        )

    async def get_job_async(self, run_id : uuid.UUID, x_user_id : uuid.UUID = Header(alias = "X-User-Id")) -> Dict[str, Any]:
        try:
            return await self.job_manager.get_job_result_async(run_id, x_user_id)
        except JobNotFoundError as job_not_found_error:
            raise HTTPException(status_code = 404, detail = str(job_not_found_error)) from job_not_found_error

    async def cancel_job_async(self, run_id : uuid.UUID, x_user_id : uuid.UUID = Header(alias = "X-User-Id")) -> Dict[str, Any]:
        try:
            return await self.job_manager.cancel_async(run_id, x_user_id)
        except JobNotFoundError as job_not_found_error:
            raise HTTPException(status_code = 404, detail = str(job_not_found_error)) from job_not_found_error
        except JobStateError as job_state_error:
            raise HTTPException(status_code = 409, detail = str(job_state_error)) from job_state_error

    async def get_job_list_async(self, x_user_id : uuid.UUID = Header(alias = "X-User-Id"), status : Optional[str] = Query(default = None), job_type : Optional[str] = Query(default = None), cursor : Optional[str] = Query(default = None), limit : int = Query(default = 20, ge = 1, le = 100)) -> Dict[str, Any]:
        if status is not None:
            try:
                JobStatus(status)
            except ValueError as exception:
                raise HTTPException(status_code = 400, detail = "INVALID JOB STATUS") from exception
        if job_type is not None:
            try:
                JobType(job_type)
            except ValueError as exception:
                raise HTTPException(status_code = 400, detail = "INVALID JOB TYPE") from exception

        cursor_created_at, cursor_run_id = LLMAPIRouter._decode_cursor(cursor)
        job_dictionary_list = await self.job_manager.get_job_list_async(
            x_user_id,
            status,
            job_type,
            cursor_created_at,
            cursor_run_id,
            limit
        )
        next_cursor = LLMAPIRouter._encode_cursor(job_dictionary_list[-1]) if len(job_dictionary_list) == limit else None
        return {"job_list" : job_dictionary_list, "next_cursor" : next_cursor}
