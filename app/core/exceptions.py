from fastapi import HTTPException, status


class JobNotFoundError(HTTPException):
    def __init__(self, job_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id '{job_id}' was not found.",
        )


class JobAlreadyCancelledError(HTTPException):
    def __init__(self, job_id: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job '{job_id}' is already cancelled or completed and cannot be modified.",
        )


class InvalidJobPayloadError(HTTPException):
    def __init__(self, detail: str = "Invalid job payload."):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )
