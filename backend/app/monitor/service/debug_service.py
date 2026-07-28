##################################################
# 디버그 서비스 (Redis 스냅샷 / API 테스트 페이지)
#
# 개발자 모드 패널에서만 쓰는 조회 기능이다. 운영 로직에 영향을 주지 않는다.
##################################################

import json
import os

from typing import Any
from typing import Dict
from typing import Optional

from fastapi           import HTTPException
from fastapi.responses import FileResponse

from app.monitor.service.auth_service import AuthService


class DebugService:
    MATCHED_KEY_MAXIMUM_COUNT = 50    # 디버그 표시용 상한
    LIST_TAIL_ITEM_COUNT      = 30    # 리스트는 최근 30개만 보여준다
    SCAN_COUNT_HINT           = 200

    def __init__(self, orchestrator_redis_client : Any, auth_service : AuthService,
                 project_root_directory_path : str) -> None:
        self.orchestrator_redis_client   = orchestrator_redis_client
        self.auth_service                = auth_service
        self.project_root_directory_path = project_root_directory_path

    @staticmethod
    def _to_text(raw_value : Any) -> str:
        # Redis 응답 정규화 : decode_responses 설정과 무관하게 항상 str 로 만든다 (bytes 면 디코드)
        return raw_value.decode("utf-8", errors = "replace") if isinstance(raw_value, bytes) else str(raw_value)

    @staticmethod
    def _try_parse_json(raw_value : Any) -> Any:
        text = DebugService._to_text(raw_value)
        try:
            return json.loads(text)
        except Exception:
            return text

    async def get_api_client_page_async(self) -> FileResponse:
        # 새 창(/dev/api-client)으로 여는 API 테스트 페이지 :
        # 백엔드가 직접 서빙하므로 origin = API 베이스 (CORS 불필요)
        frontend_file_path = os.path.join(
            self.project_root_directory_path, "frontend", "public", "legacy", "api_client.html")
        if not os.path.isfile(frontend_file_path):
            raise HTTPException(status_code = 404, detail = f"API CLIENT PAGE NOT FOUND : {frontend_file_path}")
        return FileResponse(frontend_file_path, media_type = "text/html")

    async def get_redis_snapshot_async(self, thread_id : str, authorization : Optional[str]) -> Dict[str, Any]:
        # 디버그 패널용 : 해당 스레드와 관련된 Redis 키를 실시간 스냅샷으로 반환한다
        # (런 청크 버퍼 키 형식 : orch:{thread_id}:run:{run_id}:chunk_list)
        user_id = self.auth_service.require_authenticated_user_id(authorization)
        await self.auth_service.assert_thread_accessible_async(user_id, thread_id)
        redis_client = self.orchestrator_redis_client

        try:
            matched_key_list = []
            async for key_value in redis_client.scan_iter(match = f"*{thread_id}*", count = DebugService.SCAN_COUNT_HINT):
                matched_key_list.append(DebugService._to_text(key_value))
                if len(matched_key_list) >= DebugService.MATCHED_KEY_MAXIMUM_COUNT:
                    break

            key_snapshot_list = []
            for key_name in sorted(matched_key_list):
                key_type         = DebugService._to_text(await redis_client.type(key_name))
                ttl_second_count = await redis_client.ttl(key_name)
                if key_type == "list":
                    total_length = await redis_client.llen(key_name)
                    value        = [DebugService._try_parse_json(item)
                                    for item in await redis_client.lrange(key_name, -DebugService.LIST_TAIL_ITEM_COUNT, -1)]
                elif key_type == "hash":
                    total_length = await redis_client.hlen(key_name)
                    value        = {DebugService._to_text(field) : DebugService._try_parse_json(item)
                                    for field, item in (await redis_client.hgetall(key_name)).items()}
                elif key_type == "string":
                    total_length = 1
                    value        = DebugService._try_parse_json(await redis_client.get(key_name))
                else:
                    total_length = None
                    value        = f"(미지원 타입 : {key_type})"
                key_snapshot_list.append({"key" : key_name, "type" : key_type,
                                          "ttl_second" : ttl_second_count, "length" : total_length, "value" : value})
            return {"thread_id" : thread_id, "matched_key_count" : len(matched_key_list), "keys" : key_snapshot_list}
        except Exception as exception:
            raise HTTPException(status_code = 502, detail = f"REDIS SNAPSHOT FAILED : {exception}")
