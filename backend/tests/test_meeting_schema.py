import pytest

from app.schemas.meetings import MeetingCreate


@pytest.mark.parametrize("source_type", ["direct", "txt", "pdf", "audio"])
def test_meeting_create_accepts_supported_source_types(source_type: str) -> None:
    payload = MeetingCreate.model_validate(
        {
            "team_id": "11111111-1111-4111-8111-111111111111",
            "title": "Source type validation",
            "meeting_at": "2026-11-12T09:00:00+09:00",
            "source_type": source_type,
        }
    )

    assert payload.source_type == source_type
