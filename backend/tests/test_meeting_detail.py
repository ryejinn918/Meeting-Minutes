from typing import Any
from uuid import UUID

import pytest

from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.services.meetings import MeetingService

USER_ID = UUID("11111111-1111-4111-8111-111111111111")
TEAM_ID = UUID("22222222-2222-4222-8222-222222222222")
MEETING_ID = UUID("38453cc8-34c9-4065-8703-9efda938211e")
TRANSCRIPT_ID = UUID("33333333-3333-4333-8333-333333333333")
NOTES_ID = UUID("44444444-4444-4444-8444-444444444444")
RUN_ID = UUID("55555555-5555-4555-8555-555555555555")


class DetailRepository:
    def __init__(self, *, analyzed: bool = False, member: bool = True) -> None:
        self.analyzed = analyzed
        self.member = member
        self.action_source_run_id: UUID | None = None
        self.meeting = {
            "id": str(MEETING_ID),
            "team_id": str(TEAM_ID),
            "title": "상세 조회 회의",
            "meeting_at": "2026-11-11T09:00:00+09:00",
            "created_by": str(USER_ID),
            "processing_status": "ready" if analyzed else "draft",
            "current_transcript_id": str(TRANSCRIPT_ID),
            "current_notes_id": str(NOTES_ID) if analyzed else None,
            "version": 2,
        }

    async def get_meeting(self, meeting_id: UUID) -> dict[str, Any] | None:
        return self.meeting if meeting_id == MEETING_ID else None

    async def get_membership(self, team_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        if not self.member:
            return None
        return {"team_id": str(team_id), "user_id": str(user_id), "role": "owner"}

    async def get_profiles(self, user_ids: set[UUID]) -> dict[str, dict[str, Any]]:
        return {
            str(USER_ID): {
                "id": str(USER_ID),
                "display_name": "작성자",
                "email": "owner@example.invalid",
                "avatar_url": None,
            }
        }

    async def get_transcript(self, transcript_id: UUID | None) -> dict[str, Any] | None:
        if transcript_id != TRANSCRIPT_ID:
            return None
        return {
            "id": str(TRANSCRIPT_ID),
            "original_text": "변경되면 안 되는 원문",
            "edited_text": "사용자가 편집한 전문",
        }

    async def get_notes(self, notes_id: UUID | None) -> dict[str, Any] | None:
        if not self.analyzed or notes_id != NOTES_ID:
            return None
        return {
            "summary": "분석 요약",
            "key_discussions": [{"id": "discussion-1", "text": "논의", "evidence": None}],
            "decisions": [],
            "follow_ups": [],
            "derived_from_run_id": str(RUN_ID),
        }

    async def get_ai_run(self, run_id: UUID | None) -> dict[str, Any] | None:
        if run_id != RUN_ID:
            return None
        return {"id": str(RUN_ID), "completed_at": "2026-11-11T01:00:00Z"}

    async def list_action_items(
        self, meeting_id: UUID, source_run_id: UUID | None = None
    ) -> list[dict[str, Any]]:
        self.action_source_run_id = source_run_id
        if not self.analyzed:
            return []
        return [
            {
                "id": "66666666-6666-4666-8666-666666666666",
                "description": "후속 업무",
                "assignee_id": None,
                "assignee_text": None,
                "due_date": None,
                "status": "todo",
            }
        ]

    async def list_shared_member_ids(self, meeting_id: UUID) -> list[UUID]:
        return []

    async def list_transcript_speakers(
        self, transcript_id: UUID | None
    ) -> list[dict[str, Any]]:
        return []

    async def list_transcript_segments(
        self, transcript_id: UUID | None
    ) -> list[dict[str, Any]]:
        return []


def make_service(repository: DetailRepository) -> MeetingService:
    return MeetingService(
        repository,  # type: ignore[arg-type]
        AuthenticatedUser(id=USER_ID, email="owner@example.invalid", access_token="test"),
    )


@pytest.mark.asyncio
async def test_existing_draft_detail_returns_empty_ai_fields_and_original() -> None:
    repository = DetailRepository()

    result = await make_service(repository).get(MEETING_ID)

    assert result.summary == ""
    assert result.key_discussions == []
    assert result.action_items == []
    assert result.ai_generated_at is None
    assert result.transcript_original == "변경되면 안 되는 원문"
    assert result.transcript_edited == "사용자가 편집한 전문"
    assert repository.action_source_run_id is None


@pytest.mark.asyncio
async def test_analyzed_detail_returns_notes_run_metadata_and_actions() -> None:
    repository = DetailRepository(analyzed=True)

    result = await make_service(repository).get(MEETING_ID)

    assert result.summary == "분석 요약"
    assert result.key_discussions[0].text == "논의"
    assert len(result.action_items) == 1
    assert result.action_items[0].assignee_name is None
    assert result.ai_generated_at is not None
    assert repository.action_source_run_id == RUN_ID
    assert result.transcript_original == "변경되면 안 되는 원문"


@pytest.mark.asyncio
async def test_missing_meeting_returns_404() -> None:
    repository = DetailRepository()

    with pytest.raises(AppError) as error:
        await make_service(repository).get(UUID("99999999-9999-4999-8999-999999999999"))

    assert error.value.status_code == 404
    assert error.value.code == "MEETING_NOT_FOUND"


@pytest.mark.asyncio
async def test_other_team_member_is_denied() -> None:
    repository = DetailRepository(member=False)

    with pytest.raises(AppError) as error:
        await make_service(repository).get(MEETING_ID)

    assert error.value.status_code == 403
    assert error.value.code == "TEAM_ACCESS_DENIED"
