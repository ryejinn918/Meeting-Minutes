from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class MeetingCreate(BaseModel):
    team_id: UUID
    title: str = Field(min_length=1, max_length=100)
    meeting_at: datetime
    source_type: Literal["direct", "txt", "pdf", "audio"] = "direct"


class MeetingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    meeting_at: datetime | None = None
    version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_change(self) -> "MeetingUpdate":
        if self.title is None and self.meeting_at is None:
            raise ValueError("수정할 제목 또는 회의 날짜가 필요합니다.")
        return self


class TranscriptUpsert(BaseModel):
    text: str = Field(min_length=1, max_length=500_000)


class EditableDiscussionItem(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=2000)
    evidence: str | None = Field(default=None, max_length=1000)


class MeetingNotesUpdate(BaseModel):
    summary: str = Field(min_length=1, max_length=5000)
    key_discussions: list[EditableDiscussionItem] = Field(max_length=50)
    decisions: list[EditableDiscussionItem] = Field(max_length=50)
    follow_ups: list[EditableDiscussionItem] = Field(max_length=50)
    version: int = Field(ge=1)


class UserSummary(BaseModel):
    id: UUID
    name: str
    email: str
    avatar_url: str | None = None


class DiscussionItem(BaseModel):
    id: str
    text: str
    evidence: str | None = None


class ActionItemResponse(BaseModel):
    id: UUID
    description: str
    assignee_id: UUID | None
    assignee_name: str | None
    due_date: date | None
    status: Literal["todo", "in_progress", "done"]


class MeetingResponse(BaseModel):
    id: UUID
    team_id: UUID
    title: str
    meeting_at: datetime
    created_by: UserSummary
    processing_status: str
    version: int
    is_mine: bool
    is_shared_with_me: bool
    summary: str = ""
    transcript_original: str = ""
    transcript_edited: str = ""
    key_discussions: list[DiscussionItem] = Field(default_factory=list)
    decisions: list[DiscussionItem] = Field(default_factory=list)
    follow_ups: list[DiscussionItem] = Field(default_factory=list)
    action_items: list[ActionItemResponse] = Field(default_factory=list)
    shared_member_ids: list[UUID] = Field(default_factory=list)
    ai_generated_at: datetime | None = None


def normalize_items(value: Any) -> list[DiscussionItem]:
    if not isinstance(value, list):
        return []
    return [DiscussionItem.model_validate(item) for item in value if isinstance(item, dict)]
