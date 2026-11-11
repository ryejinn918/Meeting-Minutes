from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnalysisListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    evidence: str | None = Field(max_length=1000)

    @field_validator("text", "evidence")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class AnalysisActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=2000)
    assignee_name: str | None = Field(max_length=100)
    due_date: date | None
    status: Literal["todo"]
    evidence: str | None = Field(max_length=1000)

    @field_validator("description", "assignee_name", "evidence")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class MeetingAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=5000)
    key_discussions: list[AnalysisListItem] = Field(max_length=50)
    decisions: list[AnalysisListItem] = Field(max_length=50)
    action_items: list[AnalysisActionItem] = Field(max_length=100)
    follow_ups: list[AnalysisListItem] = Field(max_length=50)

    @field_validator("summary")
    @classmethod
    def strip_summary(cls, value: str) -> str:
        return value.strip()
