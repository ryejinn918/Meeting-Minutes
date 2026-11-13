from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

MeetingType = Literal["general", "project", "interview", "workshop"]
QuestionCategory = Literal["decision", "assignee", "due_date", "number", "name", "speaker", "other"]


class TemplateSection(BaseModel):
    key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=100)


class MeetingTemplateCreate(BaseModel):
    organization_id: UUID | None = None
    department_id: UUID | None = None
    team_id: UUID | None = None
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)
    meeting_type: MeetingType
    sections: list[TemplateSection] = Field(min_length=1, max_length=20)
    writing_rules: str = Field(default="", max_length=3000)
    is_default: bool = False


class MeetingTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    sections: list[TemplateSection] | None = Field(default=None, min_length=1, max_length=20)
    writing_rules: str | None = Field(default=None, max_length=3000)
    is_default: bool | None = None
    is_active: bool | None = None


class MeetingTemplateResponse(MeetingTemplateCreate):
    id: str
    version: int
    is_active: bool
    is_builtin: bool = False
    created_at: datetime | None = None


class GlossaryTermCreate(BaseModel):
    organization_id: UUID | None = None
    department_id: UUID | None = None
    team_id: UUID | None = None
    term: str = Field(min_length=1, max_length=200)
    preferred_term: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=30)
    description: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def require_scope(self) -> "GlossaryTermCreate":
        if self.organization_id is None and self.team_id is None:
            raise ValueError("조직 또는 팀 범위를 지정해 주세요.")
        if self.department_id is not None and self.organization_id is None:
            raise ValueError("부문 용어에는 조직이 필요합니다.")
        self.aliases = [item.strip() for item in self.aliases if item.strip()]
        return self


class GlossaryTermUpdate(BaseModel):
    term: str | None = Field(default=None, min_length=1, max_length=200)
    preferred_term: str | None = Field(default=None, min_length=1, max_length=200)
    aliases: list[str] | None = Field(default=None, max_length=30)
    description: str | None = Field(default=None, max_length=1000)


class GlossaryTermResponse(GlossaryTermCreate):
    id: UUID
    created_at: datetime


class AttendeeInput(BaseModel):
    user_id: UUID | None = None
    external_name: str | None = Field(default=None, min_length=1, max_length=100)
    external_organization: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def exactly_one_identity(self) -> "AttendeeInput":
        if (self.user_id is None) == (self.external_name is None):
            raise ValueError("팀원 또는 외부 참석자 이름 중 하나만 지정해 주세요.")
        return self


class AttendeeResponse(AttendeeInput):
    id: UUID
    display_name: str


class CorrectionChange(BaseModel):
    original: str = Field(min_length=1, max_length=300)
    corrected: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=500)


class CorrectionUncertainty(BaseModel):
    category: QuestionCategory
    question: str = Field(min_length=1, max_length=1000)
    evidence: str | None = Field(default=None, max_length=1000)


class TranscriptCorrectionResult(BaseModel):
    corrected_text: str = Field(min_length=1, max_length=500_000)
    changes: list[CorrectionChange] = Field(default_factory=list, max_length=200)
    uncertainties: list[CorrectionUncertainty] = Field(default_factory=list, max_length=50)


class QuestionCreate(BaseModel):
    category: QuestionCategory
    question: str = Field(min_length=1, max_length=1000)
    evidence: str | None = Field(default=None, max_length=1000)


class QuestionAnswer(BaseModel):
    answer: str | None = Field(default=None, max_length=2000)
    status: Literal["answered", "dismissed"]

    @model_validator(mode="after")
    def answered_requires_text(self) -> "QuestionAnswer":
        if self.status == "answered" and not (self.answer or "").strip():
            raise ValueError("답변을 입력해 주세요.")
        return self


class QuestionResponse(QuestionCreate):
    id: UUID
    answer: str | None
    status: Literal["pending", "answered", "dismissed"]
    created_at: datetime
    answered_at: datetime | None


class SegmentSpeakerUpdate(BaseModel):
    speaker_id: UUID
    scope: Literal["single", "following"] = "single"


class SpeakerEditResponse(BaseModel):
    batch_id: UUID
    changed_count: int


class MeetingReviewRequest(BaseModel):
    status: Literal["review_required", "approved", "rejected"]
    note: str = Field(default="", max_length=2000)


class MeetingReviewResponse(BaseModel):
    status: Literal["draft", "review_required", "approved", "rejected"]
    note: str
    version: int
    created_at: datetime


class VoiceProfileRequest(BaseModel):
    consented: bool
    label: str = Field(default="", max_length=100)


class VoiceProfileResponse(BaseModel):
    id: UUID
    team_id: UUID
    user_id: UUID
    label: str
    consented_at: datetime | None
    revoked_at: datetime | None


class QualityOptionsResponse(BaseModel):
    templates: list[MeetingTemplateResponse]
    glossary_terms: list[GlossaryTermResponse]
