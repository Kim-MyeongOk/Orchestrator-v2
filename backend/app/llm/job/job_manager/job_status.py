from enum import Enum

class JobStatus(Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"

    def is_terminal(self) -> bool:
        return self in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
