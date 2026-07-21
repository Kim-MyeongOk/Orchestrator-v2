##################################################
# 잡 파이프라인 일괄 flush 테스트
# 실행 중에는 DB 쓰기가 없고(Redis 발행만), 종료 시점에 한 번에 적재되는지 검증한다.
# 또한 청크 유실(실패 + 청크 0건) 판정 로직을 확인한다.
##################################################

from app.llm.job.job_executor.job_executor       import JobExecutor
from app.llm.job.job_manager.job_manager         import JobManager
from app.llm.job.job_manager.job_status          import JobStatus
from app.llm.stream_pipeline.normalized_chunk    import NormalizedChunk
from app.llm.stream_pipeline.message_accumulator import MessageAccumulator


def _create_normalized_chunk(sequence_number : int, chunk_type : str) -> NormalizedChunk:
    return NormalizedChunk(
        sequence        = sequence_number,
        chunk_type      = chunk_type,
        namespace_list  = [],
        namespace_path  = "",
        data_dictionary = {"value" : f"chunk-{sequence_number}"},
        created_at      = "2026-07-21T00:00:00+00:00"
    )


def _create_empty_pending_flush_dictionary() -> dict:
    return {"chunk_list" : [], "event_chunk_list" : [], "task_projection_list" : [], "streamed_message_list" : []}


class TestBulkFlushBuffering:
    def test_chunks_are_buffered_not_written_immediately(self):
        # 실행 중 청크는 메모리 버퍼에만 쌓인다 (DB 쓰기 없음)
        pending_flush_dictionary = _create_empty_pending_flush_dictionary()
        message_accumulator      = MessageAccumulator()
        for sequence_number in range(1, 6):
            JobExecutor._buffer_chunk(_create_normalized_chunk(sequence_number, "tasks"), message_accumulator, pending_flush_dictionary)
        assert len(pending_flush_dictionary["chunk_list"]) == 5
        assert [chunk.sequence for chunk in pending_flush_dictionary["chunk_list"]] == [1, 2, 3, 4, 5]

    def test_task_and_custom_chunks_become_events(self):
        # tasks / custom 청크는 이벤트 버퍼로도 분류된다
        pending_flush_dictionary = _create_empty_pending_flush_dictionary()
        message_accumulator      = MessageAccumulator()
        JobExecutor._buffer_chunk(_create_normalized_chunk(1, "tasks"),  message_accumulator, pending_flush_dictionary)
        JobExecutor._buffer_chunk(_create_normalized_chunk(2, "custom"), message_accumulator, pending_flush_dictionary)
        assert len(pending_flush_dictionary["event_chunk_list"]) == 2
        assert len(pending_flush_dictionary["chunk_list"])       == 2

    def test_messages_chunk_is_not_treated_as_event(self):
        # messages 청크는 이벤트가 아니라 메시지 누적기로 간다
        pending_flush_dictionary = _create_empty_pending_flush_dictionary()
        message_accumulator      = MessageAccumulator()
        JobExecutor._buffer_chunk(_create_normalized_chunk(1, "messages"), message_accumulator, pending_flush_dictionary)
        assert pending_flush_dictionary["event_chunk_list"] == []
        assert len(pending_flush_dictionary["chunk_list"])  == 1


class TestLostJobDetection:
    def test_failed_job_without_chunk_is_lost(self):
        # 실패 + 청크 0건 → 유실로 판정 (재호출 대상)
        assert JobManager.is_lost_job({"status" : JobStatus.FAILED.value, "chunk_count" : 0}) is True
        assert JobManager.is_lost_job({"status" : JobStatus.FAILED.value}) is True   # chunk_count 없음도 0 취급

    def test_failed_job_with_chunk_is_not_lost(self):
        # 실패했지만 청크가 남아 있으면 재호출하지 않는다 (부분 적재분 보존)
        assert JobManager.is_lost_job({"status" : JobStatus.FAILED.value, "chunk_count" : 3}) is False

    def test_completed_job_is_not_lost(self):
        # 정상 완료 작업은 재호출 대상이 아니다
        assert JobManager.is_lost_job({"status" : JobStatus.COMPLETED.value, "chunk_count" : 0}) is False
        assert JobManager.is_lost_job({"status" : JobStatus.CANCELLED.value, "chunk_count" : 0}) is False
