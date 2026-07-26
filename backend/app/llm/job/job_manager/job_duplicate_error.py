class JobDuplicateError(Exception):
    def __init__(self, existing_run_id : str) -> None:
        self.existing_run_id = existing_run_id
        super().__init__(f"DUPLICATE JOB : {existing_run_id}")
