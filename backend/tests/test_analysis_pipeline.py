from copy import deepcopy
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.ai.analysis.mock_provider import MockAnalysisProvider
from app.ai.pipeline import AnalysisService
from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.core.settings import Settings

USER_ID = UUID("11111111-1111-4111-8111-111111111111")
TEAM_ID = UUID("22222222-2222-4222-8222-222222222222")
MEETING_ID = UUID("33333333-3333-4333-8333-333333333333")
TRANSCRIPT_ID = UUID("44444444-4444-4444-8444-444444444444")
JOB_ID = UUID("55555555-5555-4555-8555-555555555555")


class FakeMeetingRepository:
    def __init__(self, *, member: bool = True) -> None:
        self.meeting: dict[str, Any] = {
            "id": str(MEETING_ID),
            "team_id": str(TEAM_ID),
            "title": "회의",
            "meeting_at": "2026-11-11T09:00:00+09:00",
            "created_by": str(USER_ID),
            "processing_status": "draft",
            "current_transcript_id": str(TRANSCRIPT_ID),
            "current_notes_id": None,
            "version": 1,
        }
        self.transcript = {
            "id": str(TRANSCRIPT_ID),
            "original_text": "보존되어야 할 원본",
            "edited_text": "김민지가 API 연결을 진행하기로 했다.",
        }
        self.member = member

    async def get_meeting(self, meeting_id: UUID) -> dict[str, Any] | None:
        return self.meeting if meeting_id == MEETING_ID else None

    async def get_transcript(self, transcript_id: UUID | None) -> dict[str, Any] | None:
        return self.transcript if transcript_id == TRANSCRIPT_ID else None

    async def get_membership(self, team_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        if not self.member:
            return None
        return {"team_id": str(team_id), "user_id": str(user_id), "role": "owner"}

    async def update_meeting(
        self, meeting_id: UUID, version: int, values: dict[str, Any]
    ) -> dict[str, Any] | None:
        if version != self.meeting["version"]:
            return None
        self.meeting.update(values)
        self.meeting["version"] = version + 1
        return self.meeting


class FakeAIRepository:
    def __init__(self) -> None:
        self.job = {
            "id": str(JOB_ID),
            "meeting_id": str(MEETING_ID),
            "job_type": "analyze",
            "status": "queued",
            "attempt_count": 0,
            "error_code": None,
            "error_message_safe": None,
            "started_at": None,
            "finished_at": None,
            "created_at": "2026-11-11T00:00:00Z",
        }
        self.active: dict[str, Any] | None = None
        self.runs: list[dict[str, Any]] = []
        self.notes: list[dict[str, Any]] = []
        self.actions: list[dict[str, Any]] = []

    async def get_active_job(self, meeting_id: UUID) -> dict[str, Any] | None:
        return self.active

    async def create_job(self, meeting_id: UUID) -> dict[str, Any]:
        return self.job

    async def get_job(self, job_id: UUID) -> dict[str, Any] | None:
        return self.job if job_id == JOB_ID else None

    async def update_job(self, job_id: UUID, values: dict[str, Any]) -> dict[str, Any]:
        self.job.update(values)
        return self.job

    async def create_ai_run(self, **values: Any) -> UUID:
        run_id = uuid4()
        self.runs.append({"id": run_id, **values})
        return run_id

    async def create_notes(self, **values: Any) -> UUID:
        notes_id = uuid4()
        self.notes.append({"id": notes_id, **values})
        return notes_id

    async def create_action_items(self, items: list[dict[str, Any]]) -> None:
        self.actions.extend(items)


def service(
    user_repository: FakeMeetingRepository,
    admin_ai_repository: FakeAIRepository,
) -> AnalysisService:
    return AnalysisService(
        user_repository=user_repository,  # type: ignore[arg-type]
        user_ai_repository=admin_ai_repository,  # type: ignore[arg-type]
        admin_repository=user_repository,  # type: ignore[arg-type]
        admin_ai_repository=admin_ai_repository,  # type: ignore[arg-type]
        user=AuthenticatedUser(id=USER_ID, email="owner@example.invalid", access_token="test"),
        provider=MockAnalysisProvider(),
        settings=Settings(_env_file=None, ai_mode="mock"),
    )


@pytest.mark.asyncio
async def test_success_preserves_transcript_and_separates_run_from_editable_notes() -> None:
    repository = FakeMeetingRepository()
    ai_repository = FakeAIRepository()
    original = deepcopy(repository.transcript)

    await service(repository, ai_repository).run(JOB_ID)

    assert repository.transcript == original
    assert len(ai_repository.runs) == 1
    assert len(ai_repository.notes) == 1
    assert ai_repository.notes[0]["run_id"] == ai_repository.runs[0]["id"]
    assert len(ai_repository.actions) == 1
    assert repository.meeting["processing_status"] == "ready"
    assert repository.meeting["current_notes_id"] == str(ai_repository.notes[0]["id"])
    assert ai_repository.job["status"] == "succeeded"


@pytest.mark.asyncio
async def test_duplicate_analysis_request_is_rejected() -> None:
    repository = FakeMeetingRepository()
    ai_repository = FakeAIRepository()
    ai_repository.active = ai_repository.job

    with pytest.raises(AppError) as error:
        await service(repository, ai_repository).start(MEETING_ID)

    assert error.value.status_code == 409
    assert error.value.code == "ANALYSIS_ALREADY_RUNNING"


@pytest.mark.asyncio
async def test_non_member_cannot_start_analysis() -> None:
    repository = FakeMeetingRepository(member=False)
    ai_repository = FakeAIRepository()

    with pytest.raises(AppError) as error:
        await service(repository, ai_repository).start(MEETING_ID)

    assert error.value.status_code == 403
    assert error.value.code == "TEAM_ACCESS_DENIED"
    assert ai_repository.runs == []
