from typing import Any
from uuid import UUID

import pytest

from app.core.errors import AppError
from app.db.repositories import MeetFlowRepository


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.created_rows: dict[str, dict[str, Any]] = {}

    async def request(self, method: str, path: str, **kwargs: Any) -> tuple[Any, dict]:
        self.calls.append({"method": method, "path": path, **kwargs})
        if method == "POST":
            self.created_rows[path] = kwargs["json"]
            return None, {}
        row = self.created_rows.get(path)
        return ([row] if row else []), {}


@pytest.mark.asyncio
async def test_create_team_derives_creator_from_service_user() -> None:
    client = RecordingClient()
    repository = MeetFlowRepository(client)  # type: ignore[arg-type]
    user_id = UUID("11111111-1111-4111-8111-111111111111")

    result = await repository.create_team("AI Team", user_id)

    assert result["name"] == "AI Team"
    assert client.calls[0]["path"] == "teams"
    assert client.calls[0]["json"]["name"] == "AI Team"
    assert client.calls[0]["json"]["created_by"] == str(user_id)
    assert UUID(client.calls[0]["json"]["id"])
    assert client.calls[0]["prefer"] == "return=minimal"
    assert client.calls[1]["method"] == "GET"
    assert client.calls[1]["params"]["id"] == f"eq.{client.calls[0]['json']['id']}"


@pytest.mark.asyncio
async def test_create_meeting_avoids_insert_returning_rls_check() -> None:
    client = RecordingClient()
    repository = MeetFlowRepository(client)  # type: ignore[arg-type]
    values = {
        "team_id": "22222222-2222-4222-8222-222222222222",
        "title": "Weekly Meeting",
        "meeting_at": "2026-11-11T00:00:00+00:00",
        "source_type": "direct",
        "created_by": "11111111-1111-4111-8111-111111111111",
        "processing_status": "draft",
    }

    result = await repository.create_meeting(values)

    assert result["title"] == "Weekly Meeting"
    assert client.calls[0]["path"] == "meetings"
    assert client.calls[0]["prefer"] == "return=minimal"
    assert UUID(client.calls[0]["json"]["id"])
    assert client.calls[1]["method"] == "GET"
    assert "source_type" in client.calls[1]["params"]["select"].split(",")


@pytest.mark.asyncio
async def test_create_transcript_preserves_original_and_reads_after_insert() -> None:
    client = RecordingClient()
    repository = MeetFlowRepository(client)  # type: ignore[arg-type]
    meeting_id = UUID("22222222-2222-4222-8222-222222222222")
    user_id = UUID("11111111-1111-4111-8111-111111111111")

    result = await repository.create_transcript(meeting_id, user_id, "Original text")

    assert result["original_text"] == "Original text"
    assert result["edited_text"] == "Original text"
    assert client.calls[0]["path"] == "meeting_transcripts"
    assert client.calls[0]["prefer"] == "return=minimal"
    assert UUID(client.calls[0]["json"]["id"])
    assert client.calls[1]["method"] == "GET"


@pytest.mark.asyncio
async def test_draft_action_items_use_direct_null_filter() -> None:
    client = RecordingClient()
    repository = MeetFlowRepository(client)  # type: ignore[arg-type]
    meeting_id = UUID("22222222-2222-4222-8222-222222222222")

    await repository.list_action_items(meeting_id)

    params = client.calls[0]["params"]
    assert params["source_run_id"] == "is.null"
    assert "or" not in params


@pytest.mark.asyncio
async def test_analyzed_action_items_include_current_run_and_manual_items() -> None:
    client = RecordingClient()
    repository = MeetFlowRepository(client)  # type: ignore[arg-type]
    meeting_id = UUID("22222222-2222-4222-8222-222222222222")
    run_id = UUID("33333333-3333-4333-8333-333333333333")

    await repository.list_action_items(meeting_id, run_id)

    params = client.calls[0]["params"]
    assert params["or"] == (f"(source_run_id.eq.{run_id},source_run_id.is.null)")
    assert "source_run_id" not in params


@pytest.mark.asyncio
async def test_team_member_counts_use_one_batched_query() -> None:
    client = RecordingClient()
    repository = MeetFlowRepository(client)  # type: ignore[arg-type]
    first = UUID("22222222-2222-4222-8222-222222222222")
    second = UUID("33333333-3333-4333-8333-333333333333")

    await repository.count_team_members({first, second})

    assert len(client.calls) == 1
    params = client.calls[0]["params"]
    assert params["select"] == "team_id"
    assert params["status"] == "eq.active"
    assert str(first) in params["team_id"]
    assert str(second) in params["team_id"]


@pytest.mark.asyncio
async def test_scoped_team_insert_sends_both_scope_ids() -> None:
    client = RecordingClient()
    repository = MeetFlowRepository(client)  # type: ignore[arg-type]
    user_id = UUID("11111111-1111-4111-8111-111111111111")
    organization_id = UUID("22222222-2222-4222-8222-222222222222")
    department_id = UUID("33333333-3333-4333-8333-333333333333")

    await repository.create_team(
        "Scoped Team",
        user_id,
        organization_id=organization_id,
        department_id=department_id,
    )

    payload = client.calls[0]["json"]
    assert payload["organization_id"] == str(organization_id)
    assert payload["department_id"] == str(department_id)
    assert client.calls[0]["prefer"] == "return=minimal"


@pytest.mark.asyncio
async def test_soft_delete_uses_atomic_rpc() -> None:
    class DeleteClient:
        async def request(self, method: str, path: str, **kwargs: Any) -> tuple[Any, dict]:
            assert method == "POST"
            assert path == "rpc/soft_delete_meeting"
            assert kwargs["json"]["expected_version"] == 3
            return "deleted", {}

    repository = MeetFlowRepository(DeleteClient())  # type: ignore[arg-type]
    result = await repository.soft_delete_meeting(UUID("33333333-3333-4333-8333-333333333333"), 3)

    assert result == "deleted"


@pytest.mark.asyncio
async def test_soft_delete_rejects_invalid_rpc_response() -> None:
    class InvalidDeleteClient:
        async def request(self, *args: Any, **kwargs: Any) -> tuple[Any, dict]:
            return None, {}

    repository = MeetFlowRepository(InvalidDeleteClient())  # type: ignore[arg-type]
    with pytest.raises(AppError) as error:
        await repository.soft_delete_meeting(UUID("33333333-3333-4333-8333-333333333333"), 1)

    assert error.value.code == "MEETING_DELETE_RESPONSE_INVALID"
