##################################################
# 청크 병합 및 PostgreSQL 최종 저장 서비스
# 스트리밍이 완전히 완료된 시점에 Redis 버퍼의 청크 전체를 가져와
# 병합 규칙에 따라 가공한 뒤 llm 도메인 리포지토리를 재사용하여 단일 트랜잭션으로 저장한다.
# (advisory lock / turn_number 채번 / 소유권 검사 / 멱등 upsert 는 리포지토리가 보장)
#
# [청크 병합 규칙]
# - tasks / custom : 발생한 모든 조각을 하나의 dict 로 뭉쳐 llm_job.aggregated_event 에 저장
# - values         : 여러 상태 값 중 가장 마지막(최신) 청크만 llm_job.final_output 에 저장
# - messages       : 동일 (ns_path, message_id) 조각을 병합(Concatenate)하여 message_id 당
#                    1개 레코드로 llm_job_message 에 저장 (seq_first / seq_last 좌표 포함)
##################################################

import uuid

from typing   import Any
from typing   import Dict
from typing   import List
from typing   import Optional
from datetime import datetime

from common.database.postgresql.postgresql_pool_manager import PostgresqlPoolManager
from app.llm.job.job_manager.job_ownership_error        import JobOwnershipError
from app.llm.repository.chat_thread_repository          import ChatThreadRepository
from app.llm.repository.job_message_repository          import JobMessageRepository
from app.llm.repository.job_repository                  import JobRepository
from app.orchestrator.service.redis_chunk_buffer        import RedisChunkBuffer


class ChunkFlushService:
    ORCHESTRATOR_JOB_TYPE = "orchestrator"  # llm 도메인의 sync/async job 과 구분하는 타입 값

    def __init__(self, postgresql_pool_manager : PostgresqlPoolManager, redis_chunk_buffer : RedisChunkBuffer, job_repository : JobRepository, job_message_repository : JobMessageRepository, chat_thread_repository : ChatThreadRepository):
        self.postgresql_pool_manager = postgresql_pool_manager
        self.redis_chunk_buffer      = redis_chunk_buffer
        self.job_repository          = job_repository
        self.job_message_repository  = job_message_repository
        self.chat_thread_repository  = chat_thread_repository

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
        # 동일 (ns_path, message_id) 조각을 하나로 병합하여 message_id 당 1개 레코드로 만든다.
        # 버퍼 List 의 순번(index + 1)을 seq 좌표로 부여해 llm_job_message.seq_first / seq_last 를 채운다.
        merged_entry_dictionary : Dict[Any, Dict[str, Any]] = {}
        synthetic_id_count      = 0

        for chunk_index, chunk_dictionary in enumerate(chunk_dictionary_list):
            if chunk_dictionary.get("chunk_type") != "messages":
                continue
            sequence_number = chunk_index + 1

            role       = str(chunk_dictionary.get("role") or "ai")
            ns_path    = str(chunk_dictionary.get("namespace_path") or "")
            message_id = chunk_dictionary.get("message_id")
            if message_id is None:
                # id 가 없는 청크는 role 단위 합성 ID 로 묶는다
                synthetic_id_count = synthetic_id_count + 1
                message_id         = f"synthetic-{role}-{synthetic_id_count}"

            merge_key = (ns_path, message_id)
            if merge_key not in merged_entry_dictionary:
                merged_entry_dictionary[merge_key] = {
                    "message_id"      : str(message_id),
                    "ns_path"         : ns_path,
                    "role"            : role,
                    "content"         : chunk_dictionary.get("content") if chunk_dictionary.get("content") is not None else "",
                    "is_root_message" : ns_path == "",
                    "seq_first"       : sequence_number,
                    "seq_last"        : sequence_number
                }
            else:
                merged_entry_dictionary[merge_key]["content"]  = ChunkFlushService._merge_message_content(merged_entry_dictionary[merge_key]["content"], chunk_dictionary.get("content") or "")
                merged_entry_dictionary[merge_key]["seq_last"] = sequence_number

        # tool call 전용 청크 등 본문이 비어 있는 메시지는 저장하지 않는다 (aggregated_event 로 추적 가능)
        return [merged_entry for merged_entry in merged_entry_dictionary.values() if merged_entry["content"]]

    @staticmethod
    def _get_thread_preview(merged_message_dictionary_list : List[Dict[str, Any]]) -> Optional[str]:
        # 스레드 목록 미리보기용 : 마지막 루트 ai 메시지 본문 앞부분을 쓴다
        for merged_message_dictionary in reversed(merged_message_dictionary_list):
            if merged_message_dictionary["role"] == "ai" and merged_message_dictionary["is_root_message"]:
                return str(merged_message_dictionary["content"])[:200]
        return None

    ##################################################
    # 저장
    ##################################################

    async def _assert_thread_owner_async(self, thread_id : uuid.UUID, user_id : uuid.UUID) -> None:
        # llm 도메인과 동일한 기준(스레드 최초 job 의 user_id)으로 소유권을 강제한다
        owner_user_id = await self.job_repository.get_thread_owner_user_id_async(thread_id)
        if owner_user_id is not None and owner_user_id != str(user_id):
            raise JobOwnershipError(f"THREAD USER MISMATCH : {thread_id}")

    async def store_user_message_async(self, thread_id : uuid.UUID, run_id : uuid.UUID, user_id : uuid.UUID, user_message_content : str, files_metadata_list : Optional[List[Dict[str, Any]]] = None) -> None:
        # 사용자 질문을 스트리밍 시작 전에 llm_job_message 에 선행 적재한다 (thread upsert 포함).
        # 이후 flush 는 스트리밍 산출물만 저장하므로 중복 적재가 없다.
        await self._assert_thread_owner_async(thread_id, user_id)
        await self.chat_thread_repository.upsert_thread_on_submit_async(thread_id, user_id, run_id, [{"content" : user_message_content}])
        user_message_dictionary = {
            "message_id"      : f"user-{run_id}",
            "ns_path"         : "",
            "role"            : "human",
            "content"         : user_message_content,
            "files_metadata"  : files_metadata_list,
            "is_root_message" : True,
            "seq_first"       : 0,
            "seq_last"        : 0
        }
        await self.job_message_repository.insert_message_async(uuid.uuid4(), run_id, thread_id, user_message_dictionary)

    async def flush_buffer_to_postgres_async(self, thread_id : uuid.UUID, run_id : uuid.UUID, user_id : uuid.UUID, initial_input_dictionary : Dict[str, Any], started_at : Optional[datetime] = None) -> None:
        chunk_dictionary_list = await self.redis_chunk_buffer.get_chunk_dictionary_list_async(thread_id, run_id)

        last_values_dictionary         = ChunkFlushService._extract_last_values_dictionary(chunk_dictionary_list)
        aggregated_event_dictionary    = ChunkFlushService._create_aggregated_event_dictionary(chunk_dictionary_list)
        merged_message_dictionary_list = ChunkFlushService._create_merged_message_dictionary_list(chunk_dictionary_list)
        thread_preview                 = ChunkFlushService._get_thread_preview(merged_message_dictionary_list)
        event_count                    = len(aggregated_event_dictionary["tasks"]) + len(aggregated_event_dictionary["custom"])

        async with self.postgresql_pool_manager.get_pool().acquire() as connection:
            async with connection.transaction():
                # ① 실행 마스터 저장 : advisory lock + 소유권 검사 + turn_number 채번은 리포지토리가 수행
                await self.job_repository.insert_completed_job_async(run_id, thread_id, user_id, ChunkFlushService.ORCHESTRATOR_JOB_TYPE, "deepagents", initial_input_dictionary, last_values_dictionary, aggregated_event_dictionary, len(merged_message_dictionary_list), event_count, len(chunk_dictionary_list), len(chunk_dictionary_list), started_at, connection = connection)

                # ② 병합 완료 메시지 저장 : ON CONFLICT 멱등 upsert ((run_id, ns_path, message_id) 당 1개 레코드)
                for merged_message_dictionary in merged_message_dictionary_list:
                    await self.job_message_repository.insert_message_async(uuid.uuid4(), run_id, thread_id, merged_message_dictionary, connection = connection)

                # ③ 스레드 최신 상태 갱신 (user_id 가드 포함)
                await self.chat_thread_repository.update_thread_on_finish_async(thread_id, user_id, run_id, "completed", thread_preview, connection = connection)

        # ④ 저장이 커밋된 뒤에만 Redis 버퍼를 정리한다 (실패 시 TTL 로 자동 소멸)
        await self.redis_chunk_buffer.delete_buffer_async(thread_id, run_id)
        print(f"FLUSH COMPLETED : {run_id} - {len(merged_message_dictionary_list)} MERGED MESSAGES")
