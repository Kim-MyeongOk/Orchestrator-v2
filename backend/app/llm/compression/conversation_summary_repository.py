from typing import Optional
from typing import Tuple

from app.database.table_query.chat_room_query import ChatRoomQuery


##################################################
# 대화 요약 저장소 (chat_room.summary)
#
# 요약문은 체크포인트가 아니라 chat_room 에 둔다. 체크포인트는 "원본 대화"이고
# 요약은 "그 원본을 압축한 파생물"이라 수명과 갱신 주기가 다르기 때문이다.
# summarized_message_count 는 "어디까지 요약에 반영했는가"를 가리키며,
# 이 값이 없으면 압축할 때마다 이미 요약한 옛 대화를 다시 요약해 비용이 중복된다.
#
# 스레드 하나에 방 하나가 대응하므로(chat_room.thread_id) thread_id 로 조회한다.
##################################################
class ConversationSummaryRepository:
    def __init__(self, checkpoint_connection_pool) -> None:
        self.checkpoint_connection_pool = checkpoint_connection_pool

    async def get_summary_state_async(self, thread_id : str) -> Tuple[Optional[str], int]:
        # (요약문, 요약에 반영된 메시지 개수) 를 반환한다. 방이 아직 없으면 (None, 0)
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute(ChatRoomQuery.SELECT_SUMMARY, (thread_id,))
            summary_row = await cursor.fetchone()
        if summary_row is None:
            return None, 0
        return summary_row["summary"], summary_row["summarized_message_count"] or 0

    async def update_summary_async(self, thread_id : str, summary : str, summarized_message_count : int) -> None:
        async with self.checkpoint_connection_pool.connection() as connection:
            await connection.execute(
                ChatRoomQuery.UPDATE_SUMMARY, (summary, summarized_message_count, thread_id))

    async def clear_summary_async(self, thread_id : str) -> None:
        # 질문 수정으로 대화가 절단된 경우 : 요약이 사라진 대화를 가리키게 되므로 초기화한다
        async with self.checkpoint_connection_pool.connection() as connection:
            await connection.execute(ChatRoomQuery.CLEAR_SUMMARY, (thread_id,))
