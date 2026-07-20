##################################################
# CheckpointRetentionService 유닛 테스트 (DB 불필요)
# 생성자 가드레일 파라미터 검증 + 커맨드 상태 파싱 검증.
# SQL 동작 자체는 라이브 DB 검증 스크립트로 확인한다 (시딩 → 실행 → 카운트 검증).
#
# 실행 : .venv\Scripts\python.exe -m pytest -v
##################################################

import pytest

from app.orchestrator.service.checkpoint_retention_service import CheckpointRetentionService


class TestCheckpointRetentionServiceValidation:
    def test_valid_parameters_accepted(self):
        service = CheckpointRetentionService(postgresql_pool_manager = object(), keep_checkpoint_count = 20, idle_day_count = 30, delete_chunk_size = 500, chunk_sleep_second_count = 0.05)
        assert service.keep_checkpoint_count == 20
        assert service.idle_day_count        == 30
        assert service.delete_chunk_size     == 500

    def test_keep_checkpoint_count_below_one_rejected(self):
        # 0개 유지 = 전체 삭제와 같으므로 복원 불능 상태를 만들기 전에 막아야 한다
        with pytest.raises(ValueError, match = "KEEP CHECKPOINT COUNT"):
            CheckpointRetentionService(postgresql_pool_manager = object(), keep_checkpoint_count = 0)

    def test_idle_day_count_below_one_rejected(self):
        with pytest.raises(ValueError, match = "IDLE DAY COUNT"):
            CheckpointRetentionService(postgresql_pool_manager = object(), idle_day_count = 0)

    def test_delete_chunk_size_below_one_rejected(self):
        with pytest.raises(ValueError, match = "DELETE CHUNK SIZE"):
            CheckpointRetentionService(postgresql_pool_manager = object(), delete_chunk_size = 0)

    def test_negative_sleep_rejected(self):
        with pytest.raises(ValueError, match = "CHUNK SLEEP SECOND COUNT"):
            CheckpointRetentionService(postgresql_pool_manager = object(), chunk_sleep_second_count = -1.0)


class TestExtractDeletedCount:
    def test_delete_command_status_parsed(self):
        assert CheckpointRetentionService._extract_deleted_count("DELETE 123") == 123

    def test_zero_delete_parsed(self):
        assert CheckpointRetentionService._extract_deleted_count("DELETE 0") == 0
