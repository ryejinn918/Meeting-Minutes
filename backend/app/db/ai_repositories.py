from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.core.errors import AppError
from app.db.client import SupabaseRestClient

JOB_SELECT = (
    "id,meeting_id,file_id,job_type,status,attempt_count,error_code,error_message_safe,"
    "usage,started_at,finished_at,created_at,updated_at"
)


class AIRepository:
    def __init__(self, client: SupabaseRestClient) -> None:
        self.client = client

    async def create_job(
        self, meeting_id: UUID, *, job_type: str = "analyze", file_id: UUID | None = None
    ) -> dict[str, Any]:
        job_id = uuid4()
        await self.client.request(
            "POST",
            "processing_jobs",
            json={
                "id": str(job_id),
                "meeting_id": str(meeting_id),
                "job_type": job_type,
                "file_id": str(file_id) if file_id else None,
                "status": "queued",
                "attempt_count": 0,
            },
            prefer="return=minimal",
        )
        job = await self.get_job(job_id)
        if job is None:
            raise AppError(502, "JOB_CREATE_INCONSISTENT", "분석 작업을 확인할 수 없습니다.")
        return job

    async def get_job(self, job_id: UUID) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "processing_jobs",
            params={"select": JOB_SELECT, "id": f"eq.{job_id}"},
        )
        return rows[0] if rows else None

    async def get_active_job(
        self, meeting_id: UUID, *, job_type: str = "analyze"
    ) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "processing_jobs",
            params={
                "select": JOB_SELECT,
                "meeting_id": f"eq.{meeting_id}",
                "job_type": f"eq.{job_type}",
                "status": "in.(queued,processing)",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    async def update_job(self, job_id: UUID, values: dict[str, Any]) -> dict[str, Any]:
        await self.client.request(
            "PATCH",
            "processing_jobs",
            params={"id": f"eq.{job_id}"},
            json=values,
            prefer="return=minimal",
        )
        job = await self.get_job(job_id)
        if job is None:
            raise AppError(404, "JOB_NOT_FOUND", "분석 작업을 찾을 수 없습니다.")
        return job

    async def list_job_chunks(self, job_id: UUID) -> list[dict[str, Any]]:
        rows, _ = await self.client.request(
            "GET",
            "processing_job_chunks",
            params={
                "select": (
                    "chunk_index,chunk_sha256,start_seconds,end_seconds,"
                    "transcript_text,segments,provider,model,usage"
                ),
                "job_id": f"eq.{job_id}",
                "order": "chunk_index.asc",
            },
        )
        return rows

    async def save_job_chunk(
        self,
        *,
        job_id: UUID,
        chunk_index: int,
        chunk_sha256: str,
        start_seconds: float,
        end_seconds: float,
        transcript_text: str,
        segments: list[dict[str, object]],
        provider: str,
        model: str,
        usage: dict[str, Any],
    ) -> None:
        await self.client.request(
            "POST",
            "processing_job_chunks",
            params={"on_conflict": "job_id,chunk_index"},
            json={
                "job_id": str(job_id),
                "chunk_index": chunk_index,
                "chunk_sha256": chunk_sha256,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "transcript_text": transcript_text,
                "segments": segments,
                "provider": provider,
                "model": model,
                "usage": usage,
            },
            prefer="resolution=merge-duplicates,return=minimal",
        )

    async def create_ai_run(
        self,
        *,
        meeting_id: UUID,
        transcript_id: UUID,
        provider: str,
        model: str,
        validated_output: dict[str, Any],
        usage: dict[str, Any],
    ) -> UUID:
        run_id = uuid4()
        await self.client.request(
            "POST",
            "meeting_ai_runs",
            json={
                "id": str(run_id),
                "meeting_id": str(meeting_id),
                "transcript_id": str(transcript_id),
                "provider": provider,
                "model": model,
                "prompt_version": "meeting-analysis-v1",
                "schema_version": "meeting-analysis-v1",
                "validated_output": validated_output,
                "usage": usage,
                "completed_at": datetime.now(UTC).isoformat(),
            },
            prefer="return=minimal",
        )
        return run_id

    async def create_notes(
        self,
        *,
        meeting_id: UUID,
        run_id: UUID,
        user_id: UUID,
        summary: str,
        key_discussions: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        follow_ups: list[dict[str, Any]],
    ) -> UUID:
        notes_id = uuid4()
        await self.client.request(
            "POST",
            "meeting_notes",
            json={
                "id": str(notes_id),
                "meeting_id": str(meeting_id),
                "derived_from_run_id": str(run_id),
                "summary": summary,
                "key_discussions": key_discussions,
                "decisions": decisions,
                "follow_ups": follow_ups,
                "updated_by": str(user_id),
            },
            prefer="return=minimal",
        )
        return notes_id

    async def create_action_items(self, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        await self.client.request(
            "POST",
            "action_items",
            json=items,
            prefer="return=minimal",
        )
