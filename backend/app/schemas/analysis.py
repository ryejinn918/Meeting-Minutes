import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnalysisListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=5000)
    evidence: str | None = Field(max_length=1000)

    @field_validator("text", "evidence")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class DetailedDiscussionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=100)
    details: list[str] = Field(min_length=2, max_length=30)

    @field_validator("title", "details")
    @classmethod
    def strip_values(cls, value: str | list[str]) -> str | list[str]:
        if isinstance(value, str):
            return value.strip()
        return [item.strip() for item in value if item.strip()]


def _normalize_discussion_text(value: str) -> str:
    """Keep agenda headings short while preserving the generated detail."""
    lines = [line.strip() for line in value.replace("\r\n", "\n").split("\n") if line.strip()]
    if not lines:
        return value.strip()

    heading = lines[0].lstrip("-•* ").strip()
    details = [line.lstrip("-•* ").strip() for line in lines[1:] if line.strip()]
    if not details and ":" in heading:
        possible_heading, detail = heading.split(":", 1)
        if possible_heading.strip() and detail.strip():
            heading, details = possible_heading.strip(), [detail.strip()]

    if not details:
        # A malformed one-line response should still render as an agenda item
        # rather than allowing a long narrative to become the heading.
        match = re.search(r"[.!?。！？]", heading)
        if match and match.start() > 0:
            details = [heading[match.end() :].strip()] if heading[match.end() :].strip() else []
            heading = heading[: match.start()].strip()

    heading = re.sub(r"[.!?。！？]+$", "", heading).strip()
    if len(heading) > 25:
        if not details:
            details = [heading]
        shortened = heading[:25].rsplit(" ", 1)[0].strip()
        heading = shortened or heading[:25]

    if details:
        return heading + "\n" + "\n".join(f"- {detail}" for detail in details if detail)
    return heading


def _discussion_parts(value: str) -> tuple[str, list[str]]:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        return value.strip(), []
    heading = lines[0].lstrip("-•* ").strip()
    details = [line.lstrip("-•* ").strip() for line in lines[1:] if line.strip()]
    return heading, details


def _semantic_key(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", value.casefold())


def _merge_repeated_discussions(items: list[AnalysisListItem]) -> list[AnalysisListItem]:
    """Merge only repeated agenda headings/details; preserve distinct viewpoints."""
    merged: list[AnalysisListItem] = []
    seen_details: set[str] = set()
    for item in items:
        heading, details = _discussion_parts(item.text)
        unique_details = []
        for detail in details:
            key = _semantic_key(detail)
            if key and key in seen_details:
                continue
            if key:
                seen_details.add(key)
            unique_details.append(detail)
        detail_text = "\n".join(f"- {detail}" for detail in unique_details)
        normalized = _normalize_discussion_text(
            heading + (f"\n{detail_text}" if detail_text else "")
        )
        existing = next(
            (
                candidate
                for candidate in merged
                if _semantic_key(_discussion_parts(candidate.text)[0])
                == _semantic_key(heading)
            ),
            None,
        )
        if existing is None:
            merged.append(item.model_copy(update={"text": normalized}))
        elif unique_details:
            old_heading, old_details = _discussion_parts(existing.text)
            combined = old_heading + "\n" + "\n".join(
                [f"- {detail}" for detail in old_details + unique_details]
            )
            merged[merged.index(existing)] = existing.model_copy(
                update={"text": _normalize_discussion_text(combined)}
            )
    return merged


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


class DetailedMeetingAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=5000)
    key_discussions: list[DetailedDiscussionItem] = Field(max_length=50)
    decisions: list[AnalysisListItem] = Field(max_length=50)
    action_items: list[AnalysisActionItem] = Field(max_length=100)
    follow_ups: list[AnalysisListItem] = Field(max_length=50)


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

    @field_validator("key_discussions")
    @classmethod
    def normalize_key_discussions(cls, value: list[AnalysisListItem]) -> list[AnalysisListItem]:
        normalized = [
            item.model_copy(update={"text": _normalize_discussion_text(item.text)})
            for item in value
        ]
        return _merge_repeated_discussions(normalized)
