from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class JobResponse(BaseModel):
    id: UUID
    meeting_id: UUID
    job_type: Literal["analyze"]
    status: Literal["queued", "processing", "succeeded", "failed"]
    attempt_count: int
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
