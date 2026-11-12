import asyncio
from typing import Any
from uuid import UUID

import pytest

from app.core.security import AuthenticatedUser
from app.schemas.meetings import TranscriptSpeakerUpdate
from app.services.meetings import MeetingService

USER_ID = UUID("11111111-1111-4111-8111-111111111111")
TEAM_ID = UUID("22222222-2222-4222-8222-222222222222")
MEETING_ID = UUID("33333333-3333-4333-8333-333333333333")
TRANSCRIPT_ID = UUID("44444444-4444-4444-8444-444444444444")
SPEAKER_ID = UUID("55555555-5555-4555-8555-555555555555")


class PartialTranscriptRepository:
    def __init__(self) -> None:
        self.meeting: dict[str, Any] = {
            "id": str(MEETING_ID),
            "team_id": str(TEAM_ID),
            "title": "Integration Meeting",
            "meeting_at": "2026-11-11T00:00:00Z",
            "created_by": str(USER_ID),
            "processing_status": "draft",
            "current_transcript_id": None,
            "current_notes_id": None,
            "version": 1,
        }
        self.transcript = {
            "id": str(TRANSCRIPT_ID),
            "original_text": "Original text",
            "edited_text": "Original text",
        }

    async def get_meeting(self, meeting_id: UUID) -> dict[str, Any] | None:
        return self.meeting if meeting_id == MEETING_ID else None

    async def get_membership(self, team_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        return {"team_id": str(team_id), "user_id": str(user_id), "role": "owner"}

    async def get_latest_direct_transcript(
        self, meeting_id: UUID, user_id: UUID
    ) -> dict[str, Any] | None:
        return self.transcript

    async def create_transcript(self, meeting_id: UUID, user_id: UUID, text: str) -> dict:
        raise AssertionError("a retry must reuse the partially saved transcript")

    async def update_transcript(self, transcript_id: UUID, text: str) -> dict[str, Any]:
        assert transcript_id == TRANSCRIPT_ID
        self.transcript["edited_text"] = text
        return self.transcript

    async def update_meeting(
        self, meeting_id: UUID, version: int, values: dict[str, Any]
    ) -> dict[str, Any]:
        assert meeting_id == MEETING_ID
        assert version == 1
        self.meeting.update(values)
        self.meeting["version"] = 2
        return self.meeting

    async def get_profiles(self, user_ids: set[UUID]) -> dict[str, dict[str, Any]]:
        return {
            str(USER_ID): {
                "id": str(USER_ID),
                "display_name": "Owner",
                "email": "owner@example.invalid",
                "avatar_url": None,
            }
        }

    async def get_transcript(self, transcript_id: UUID | None) -> dict[str, Any] | None:
        return self.transcript if transcript_id == TRANSCRIPT_ID else None

    async def get_notes(self, notes_id: UUID | None) -> None:
        return None

    async def list_action_items(
        self, meeting_id: UUID, source_run_id: UUID | None = None
    ) -> list[dict[str, Any]]:
        return []

    async def list_shared_member_ids(self, meeting_id: UUID) -> list[UUID]:
        return []

    async def list_transcript_speakers(
        self, transcript_id: UUID | None
    ) -> list[dict[str, Any]]:
        if transcript_id != TRANSCRIPT_ID:
            return []
        return [
            {
                "id": str(SPEAKER_ID),
                "speaker_key": "chunk-0:A",
                "provider_label": "A",
                "display_name": "화자 1",
            }
        ]

    async def list_transcript_segments(
        self, transcript_id: UUID | None
    ) -> list[dict[str, Any]]:
        return []

    async def update_transcript_speaker(
        self, speaker_id: UUID, display_name: str
    ) -> None:
        assert speaker_id == SPEAKER_ID
        assert display_name == "김민지"


@pytest.mark.asyncio
async def test_transcript_retry_reuses_partial_row_and_preserves_original() -> None:
    repository = PartialTranscriptRepository()
    service = MeetingService(
        repository,  # type: ignore[arg-type]
        AuthenticatedUser(id=USER_ID, email="owner@example.invalid", access_token="test"),
    )

    result = await service.save_transcript(MEETING_ID, "Edited after retry")

    assert result.transcript_original == "Original text"
    assert result.transcript_edited == "Edited after retry"
    assert repository.meeting["current_transcript_id"] == str(TRANSCRIPT_ID)


@pytest.mark.asyncio
async def test_speaker_rename_updates_only_edited_transcript() -> None:
    repository = PartialTranscriptRepository()
    repository.meeting["current_transcript_id"] = str(TRANSCRIPT_ID)
    repository.transcript["original_text"] = "[00:00:01] 화자 1: 원본 발언"
    repository.transcript["edited_text"] = "[00:00:01] 화자 1: 수정한 발언"
    service = MeetingService(
        repository,  # type: ignore[arg-type]
        AuthenticatedUser(id=USER_ID, email="owner@example.invalid", access_token="test"),
    )

    await service.update_transcript_speaker(
        MEETING_ID,
        SPEAKER_ID,
        TranscriptSpeakerUpdate(display_name="김민지"),
    )

    assert repository.transcript["original_text"] == "[00:00:01] 화자 1: 원본 발언"
    assert repository.transcript["edited_text"] == "[00:00:01] 김민지: 수정한 발언"


@pytest.mark.asyncio
async def test_meeting_list_does_not_hydrate_card_rows() -> None:
    class ListRepository(PartialTranscriptRepository):
        async def list_meetings(self, team_id: UUID) -> list[dict[str, Any]]:
            assert team_id == TEAM_ID
            return [self.meeting, {**self.meeting, "id": str(UUID(int=9))}]

        async def get_transcript(self, transcript_id: UUID | None) -> dict[str, Any] | None:
            raise AssertionError("meeting cards must not load transcript details")

        async def list_shared_meeting_ids(
            self, user_id: UUID, meeting_ids: set[UUID]
        ) -> set[UUID]:
            return set()

    repository = ListRepository()
    service = MeetingService(
        repository,  # type: ignore[arg-type]
        AuthenticatedUser(id=USER_ID, email="owner@example.invalid", access_token="test"),
    )

    result = await service.list(TEAM_ID)

    assert len(result) == 2
    assert result[0].title == "Integration Meeting"
    assert not hasattr(result[0], "transcript_edited")


@pytest.mark.asyncio
async def test_meeting_detail_loads_independent_resources_concurrently() -> None:
    started: set[str] = set()
    release = asyncio.Event()

    class ConcurrentRepository(PartialTranscriptRepository):
        async def _wait(self, name: str) -> None:
            started.add(name)
            await release.wait()

        async def get_profiles(self, user_ids: set[UUID]) -> dict[str, dict[str, Any]]:
            await self._wait("profiles")
            return await super().get_profiles(user_ids)

        async def get_transcript(self, transcript_id: UUID | None) -> dict[str, Any] | None:
            await self._wait("transcript")
            return None

        async def list_transcript_speakers(
            self, transcript_id: UUID | None
        ) -> list[dict[str, Any]]:
            await self._wait("speakers")
            return []

        async def list_transcript_segments(
            self, transcript_id: UUID | None
        ) -> list[dict[str, Any]]:
            await self._wait("segments")
            return []

        async def get_notes(self, notes_id: UUID | None) -> None:
            await self._wait("notes")
            return None

        async def list_shared_member_ids(self, meeting_id: UUID) -> list[UUID]:
            await self._wait("shares")
            return []

    repository = ConcurrentRepository()
    service = MeetingService(
        repository,  # type: ignore[arg-type]
        AuthenticatedUser(id=USER_ID, email="owner@example.invalid", access_token="test"),
    )
    task = asyncio.create_task(service.get(MEETING_ID))
    for _ in range(20):
        if len(started) == 6:
            break
        await asyncio.sleep(0)

    assert started == {"profiles", "transcript", "speakers", "segments", "notes", "shares"}
    release.set()
    result = await task
    assert result.id == MEETING_ID
