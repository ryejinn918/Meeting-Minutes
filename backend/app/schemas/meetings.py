from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.quality import AttendeeInput, AttendeeResponse, MeetingType, QuestionResponse


class MeetingCreate(BaseModel):
    team_id: UUID
    title: str = Field(min_length=1, max_length=100)
    meeting_at: datetime
    source_type: Literal["direct", "txt", "pdf", "audio"] = "direct"
    topic: str = Field(default="", max_length=500)
    location: str = Field(default="", max_length=300)
    meeting_type: MeetingType = "general"
    purpose: str = Field(default="", max_length=1000)
    project_name: str = Field(default="", max_length=300)
    template_id: UUID | None = None
    attendees: list[AttendeeInput] = Field(default_factory=list, max_length=100)
    metadata_confirmed: bool = False


class MeetingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    meeting_at: datetime | None = None
    version: int | None = Field(default=None, ge=1)
    topic: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=300)
    meeting_type: MeetingType | None = None
    purpose: str | None = Field(default=None, max_length=1000)
    project_name: str | None = Field(default=None, max_length=300)
    template_id: UUID | None = None
    attendees: list[AttendeeInput] | None = Field(default=None, max_length=100)
    metadata_confirmed: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "MeetingUpdate":
        if not self.model_fields_set - {"version"}:
            raise ValueError("수정할 제목 또는 회의 날짜가 필요합니다.")
        return self


class TranscriptUpsert(BaseModel):
    text: str = Field(min_length=1, max_length=500_000)


class TranscriptSpeakerUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


class TranscriptSpeakerResponse(BaseModel):
    id: UUID
    provider_label: str
    display_name: str
    candidate_user_id: UUID | None = None
    candidate_confidence: float | None = None
    candidate_reason: str = ""
    confirmed_at: datetime | None = None


class TranscriptSegmentResponse(BaseModel):
    id: UUID
    speaker_id: UUID
    speaker_name: str
    start_seconds: float
    end_seconds: float
    text: str
    original_speaker_id: UUID | None = None


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


class MeetingListItemResponse(BaseModel):
    id: UUID
    team_id: UUID
    title: str
    meeting_at: datetime
    created_by: UserSummary
    processing_status: str
    version: int
    is_mine: bool
    is_shared_with_me: bool


class MeetingResponse(BaseModel):
    id: UUID
    team_id: UUID
    title: str
    meeting_at: datetime
    created_by: UserSummary
    processing_status: str
    review_status: str = "draft"
    approved_at: datetime | None = None
    approved_by: UUID | None = None
    approval_version: int | None = None
    version: int
    is_mine: bool
    is_shared_with_me: bool
    summary: str = ""
    transcript_original: str = ""
    transcript_edited: str = ""
    transcript_speakers: list[TranscriptSpeakerResponse] = Field(default_factory=list)
    transcript_segments: list[TranscriptSegmentResponse] = Field(default_factory=list)
    key_discussions: list[DiscussionItem] = Field(default_factory=list)
    decisions: list[DiscussionItem] = Field(default_factory=list)
    follow_ups: list[DiscussionItem] = Field(default_factory=list)
    action_items: list[ActionItemResponse] = Field(default_factory=list)
    shared_member_ids: list[UUID] = Field(default_factory=list)
    ai_generated_at: datetime | None = None
    topic: str = ""
    location: str = ""
    meeting_type: MeetingType = "general"
    purpose: str = ""
    project_name: str = ""
    template_id: UUID | None = None
    metadata_confirmed_at: datetime | None = None
    attendees: list[AttendeeResponse] = Field(default_factory=list)
    transcript_corrected: str = ""
    questions: list[QuestionResponse] = Field(default_factory=list)
    latest_speaker_edit_batch_id: UUID | None = None


def normalize_items(value: Any) -> list[DiscussionItem]:
    if not isinstance(value, list):
        return []
    return [DiscussionItem.model_validate(item) for item in value if isinstance(item, dict)]
