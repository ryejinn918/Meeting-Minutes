from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

FileKind = Literal["audio", "document"]
FileStatus = Literal["pending_upload", "uploaded", "processing", "succeeded", "failed"]


class UploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(gt=0, le=26_214_400)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")

    @field_validator("filename")
    @classmethod
    def clean_filename(cls, value: str) -> str:
        cleaned = value.replace(chr(92), "/").split("/")[-1].strip()
        if not cleaned or cleaned in {".", ".."}:
            raise ValueError("올바른 파일명을 입력해 주세요.")
        return cleaned

    @field_validator("sha256")
    @classmethod
    def normalize_sha256(cls, value: str) -> str:
        return value.lower()


class MeetingFileResponse(BaseModel):
    id: UUID
    meeting_id: UUID
    original_name: str
    mime_type: str
    size_bytes: int
    processing_status: FileStatus
    error_code: str | None = None
    created_at: datetime


class UploadUrlResponse(BaseModel):
    file: MeetingFileResponse
    bucket: str
    path: str
    token: str
    signed_url: str


class FileCompleteResponse(BaseModel):
    file: MeetingFileResponse
    job_id: UUID
    job_type: Literal["extract", "transcribe"]
