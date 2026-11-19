from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class WorkerClaimRequest(BaseModel):
    worker_id: UUID
    worker_name: str = Field(min_length=1, max_length=100)


class WorkerJob(BaseModel):
    job_id: UUID
    meeting_id: UUID
    file_id: UUID
    download_url: str
    original_name: str
    mime_type: str
    voice_profiles: list["WorkerVoiceProfile"] = Field(default_factory=list)


class WorkerVoiceProfile(BaseModel):
    profile_id: UUID
    user_id: UUID
    label: str = Field(min_length=1, max_length=100)
    download_url: str
    mime_type: str = "audio/mpeg"
    sha256: str | None = None


class WorkerClaimResponse(BaseModel):
    job: WorkerJob | None


class WorkerHeartbeatRequest(BaseModel):
    worker_id: UUID


class WorkerSegment(BaseModel):
    speaker: str = Field(min_length=1, max_length=100)
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(ge=0, allow_inf_nan=False)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_range(self) -> "WorkerSegment":
        if not self.speaker.strip() or not self.text.strip():
            raise ValueError("segment speaker and text must not be blank")
        if self.end <= self.start:
            raise ValueError("segment end must be after start")
        return self


class WorkerSpeakerCandidate(BaseModel):
    speaker: str = Field(min_length=1, max_length=100)
    candidate_user_id: UUID
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(default="voice_embedding", max_length=200)


class WorkerCompleteRequest(BaseModel):
    worker_id: UUID
    text: str = Field(min_length=1, max_length=2_000_000)
    language: str | None = None
    model: str = Field(min_length=1, max_length=100)
    segments: list[WorkerSegment] = Field(default_factory=list, max_length=50_000)
    usage: dict[str, Any] = Field(default_factory=dict)
    speaker_candidates: list[WorkerSpeakerCandidate] = Field(default_factory=list, max_length=200)


class WorkerFailRequest(BaseModel):
    worker_id: UUID
    error_code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z0-9_]+$")
    message: str = Field(min_length=1, max_length=300)
