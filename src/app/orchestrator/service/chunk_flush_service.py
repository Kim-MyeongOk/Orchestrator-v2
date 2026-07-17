##################################################
# 청크 병합 및 PostgreSQL 최종 저장 서비스
# 스트리밍이 완전히 완료된 시점에 Redis 버퍼의 청크 전체를 가져와
# 병합 규칙에 따라 가공한 뒤 단일 트랜잭션으로 저장한다.
#
# [청크 병합 규칙]
# - tasks / custom : 발생한 모든 조각을 하나의 dict 로 뭉쳐 orch_run.aggregated_event 에 저장
# - values         : 여러 상태 값 중 가장 마지막(최신) 청크만 orch_run.final_output 에 저장
# - messages       : 동일 message_id 조각을 병합(Concatenate)하여 message_id 당 1개 레코드로
#                    orch_message 에 bulk insert
##################################################

from typing   import Any
from typing   import Dict
from typing   import List
from typing   import Optional
from datetime import datetime
from datetime import timezone

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio         import AsyncSession
from sqlalchemy.ext.asyncio         import async_sessionmaker

from app.orchestrator.model.orch_message         import OrchMessage
from app.orchestrator.model.orch_run             import OrchRun
from app.orchestrator.model.orch_thread          import OrchThread
from app.orchestrator.service.redis_chunk_buffer import RedisChunkBuffer


class ChunkFlushService:
    def __init__(self, async_session_factory : async_sessionmaker, redis_chunk_buffer : RedisChunkBuffer):
        self.async_session_factory = async_session_factory
        self.redis_chunk_buffer    = redis_chunk_buffer

    ##################################################
    # 병합 규칙
    ##################################################

    @staticmethod
    def _extract_last_values_dictionary(chunk_dictionary_list : List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        # values 청크는 상태 스냅샷이므로 가장 마지막(최신) 것만 최종 출력으로 삼는다
        last_values_dictionary = None
        for chunk_dictionary in chunk_dictionary_list:
            if chunk_dictionary.get("chunk_type") == "values":
                last_values_dictionary = chunk_dictionary.get("payload")
        return last_values_dictionary

    @staticmethod
    def _create_aggregated_event_dictionary(chunk_dictionary_list : List[Dict[str, Any]]) -> Dict[str, Any]:
        # tasks / custom 청크는 발생한 전 조각을 순서대로 하나의 dict 에 뭉친다
        task_event_list   : List[Dict[str, Any]] = []
        custom_event_list : List[Dict[str, Any]] = []
        for chunk_dictionary in chunk_dictionary_list:
            chunk_type = chunk_dictionary.get("chunk_type")
            if chunk_type == "tasks":
                task_event_list.append({"namespace_path" : chunk_dictionary.get("namespace_path"), "payload" : chunk_dictionary.get("payload")})
            elif chunk_type == "custom":
                custom_event_list.append({"namespace_path" : chunk_dictionary.get("namespace_path"), "payload" : chunk_dictionary.get("payload")})
        return {
            "tasks"  : task_event_list,
            "custom" : custom_event_list
        }

    @staticmethod
    def _merge_message_content(base_content : Any, delta_content : Any) -> Any:
        # 스트리밍 델타를 이어 붙인다. 문자열끼리는 Concatenate, 리스트(멀티모달)는 extend.
        if isinstance(base_content, str) and isinstance(delta_content, str):
            return base_content + delta_content
        if isinstance(base_content, list) and isinstance(delta_content, list):
            return base_content + delta_content
        return str(base_content) + str(delta_content)

    @staticmethod
    def _create_merged_message_dictionary_list(chunk_dictionary_list : List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # 동일 (namespace_path, message_id) 조각을 하나로 병합하여 message_id 당 1개 레코드로 만든다
        merged_entry_dictionary : Dict[Any, Dict[str, Any]] = {}
        synthetic_id_count      = 0

        for chunk_dictionary in chunk_dictionary_list:
            if chunk_dictionary.get("chunk_type") != "messages":
                continue

            role       = str(chunk_dictionary.get("role") or "ai")
            message_id = chunk_dictionary.get("message_id")
            if message_id is None:
                # id 가 없는 청크는 role 단위 합성 ID 로 묶는다
                synthetic_id_count = synthetic_id_count + 1
                message_id         = f"synthetic-{role}-{synthetic_id_count}"

            merge_key = (chunk_dictionary.get("namespace_path"), message_id)
            if merge_key not in merged_entry_dictionary:
                merged_entry_dictionary[merge_key] = {
                    "message_id" : str(message_id),
                    "role"       : role,
                    "content"    : chunk_dictionary.get("content") if chunk_dictionary.get("content") is not None else ""
                }
            else:
                merged_entry_dictionary[merge_key]["content"] = ChunkFlushService._merge_message_content(merged_entry_dictionary[merge_key]["content"], chunk_dictionary.get("content") or "")

        # tool call 전용 청크 등 본문이 비어 있는 메시지는 저장하지 않는다 (aggregated_event 로 추적 가능)
        return [merged_entry for merged_entry in merged_entry_dictionary.values() if merged_entry["content"]]

    ##################################################
    # 저장
    ##################################################

    async def _upsert_thread_async(self, async_session : AsyncSession, thread_id : str) -> None:
        current_time     = datetime.now(timezone.utc)
        insert_statement = postgresql_insert(OrchThread).values(thread_id = thread_id, created_at = current_time, updated_at = current_time)
        insert_statement = insert_statement.on_conflict_do_update(index_elements = ["thread_id"], set_ = {"updated_at" : current_time})
        await async_session.execute(insert_statement)

    async def flush_buffer_to_postgres_async(self, thread_id : str, run_id : str, initial_input_dictionary : Dict[str, Any], user_message_dictionary : Optional[Dict[str, Any]] = None) -> None:
        chunk_dictionary_list = await self.redis_chunk_buffer.get_chunk_dictionary_list_async(thread_id, run_id)

        last_values_dictionary         = ChunkFlushService._extract_last_values_dictionary(chunk_dictionary_list)
        aggregated_event_dictionary    = ChunkFlushService._create_aggregated_event_dictionary(chunk_dictionary_list)
        merged_message_dictionary_list = ChunkFlushService._create_merged_message_dictionary_list(chunk_dictionary_list)

        async with self.async_session_factory() as async_session:
            async with async_session.begin():
                # ① 스레드 upsert (없으면 생성, 있으면 updated_at 갱신)
                await self._upsert_thread_async(async_session, thread_id)

                # ② run 저장 : 최초 입력값 + 마지막 values(최종 출력) + tasks/custom 병합본
                async_session.add(OrchRun(run_id = run_id, thread_id = thread_id, initial_input = initial_input_dictionary, final_output = last_values_dictionary, aggregated_event = aggregated_event_dictionary))

                # ③ 사용자 메시지 저장 (이력 복원의 시작점, files_metadata 포함 가능)
                message_order = 0
                if user_message_dictionary is not None:
                    async_session.add(OrchMessage(message_id = f"user-{run_id}", thread_id = thread_id, run_id = run_id, message_order = message_order, role = "human", content = str(user_message_dictionary.get("content") or ""), files_metadata = user_message_dictionary.get("files_metadata")))
                    message_order = message_order + 1

                # ④ 병합 완료 메시지 bulk insert (message_id 당 1개 레코드)
                orch_message_list : List[OrchMessage] = []
                for merged_message_dictionary in merged_message_dictionary_list:
                    orch_message_list.append(OrchMessage(message_id = merged_message_dictionary["message_id"], thread_id = thread_id, run_id = run_id, message_order = message_order, role = merged_message_dictionary["role"], content = str(merged_message_dictionary["content"]), files_metadata = None))
                    message_order = message_order + 1
                async_session.add_all(orch_message_list)

        # ⑤ 저장이 커밋된 뒤에만 Redis 버퍼를 정리한다 (실패 시 TTL 로 자동 소멸)
        await self.redis_chunk_buffer.delete_buffer_async(thread_id, run_id)
        print(f"FLUSH COMPLETED : {run_id} - {len(merged_message_dictionary_list)} MERGED MESSAGES")
