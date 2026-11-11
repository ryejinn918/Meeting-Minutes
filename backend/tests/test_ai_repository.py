from typing import Any
from uuid import UUID

import pytest

from app.db.ai_repositories import AIRepository


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.job: dict[str, Any] | None = None

    async def request(self, method: str, path: str, **kwargs: Any) -> tuple[Any, dict]:
        self.calls.append({"method": method, "path": path, **kwargs})
        if path == "processing_jobs" and method == "POST":
            self.job = {
                **kwargs["json"],
                "error_code": None,
                "error_message_safe": None,
                "started_at": None,
                "finished_at": None,
                "created_at": "2026-11-11T00:00:00Z",
                "updated_at": "2026-11-11T00:00:00Z",
            }
            return None, {}
        if path == "processing_jobs" and method == "GET":
            return [self.job], {}
        return None, {}


@pytest.mark.asyncio
async def test_ai_inserts_use_return_minimal_to_avoid_rls_returning_conflict() -> None:
    client = RecordingClient()
    repository = AIRepository(client)  # type: ignore[arg-type]
    meeting_id = UUID("22222222-2222-4222-8222-222222222222")
    transcript_id = UUID("33333333-3333-4333-8333-333333333333")
    user_id = UUID("11111111-1111-4111-8111-111111111111")

    job = await repository.create_job(meeting_id)
    run_id = await repository.create_ai_run(
        meeting_id=meeting_id,
        transcript_id=transcript_id,
        provider="mock",
        model="mock/deepseek",
        validated_output={"summary": "요약"},
        usage={"mock": True},
    )
    await repository.create_notes(
        meeting_id=meeting_id,
        run_id=run_id,
        user_id=user_id,
        summary="요약",
        key_discussions=[],
        decisions=[],
        follow_ups=[],
    )
    await repository.create_action_items(
        [{"id": str(user_id), "meeting_id": str(meeting_id), "description": "할 일"}]
    )

    assert job["status"] == "queued"
    post_calls = [call for call in client.calls if call["method"] == "POST"]
    assert [call["path"] for call in post_calls] == [
        "processing_jobs",
        "meeting_ai_runs",
        "meeting_notes",
        "action_items",
    ]
    assert all(call["prefer"] == "return=minimal" for call in post_calls)
