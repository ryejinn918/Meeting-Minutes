import hashlib
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from app.api.routes.workers import require_worker_token
from app.core.errors import AppError
from app.core.settings import Settings
from app.schemas.jobs import JobResponse
from app.schemas.worker import WorkerCompleteRequest, WorkerSegment
from app.services.file_ingestion import FileIngestionService
from app.services.gpu_worker import GPUWorkerService

WORKER_ID = UUID("11111111-1111-4111-8111-111111111111")
JOB_ID = UUID("22222222-2222-4222-8222-222222222222")


class RecordingClient:
    def __init__(self, response: Any = None) -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def request(self, method: str, path: str, *, json: dict[str, Any]) -> tuple[Any, dict]:
        self.calls.append((method, path, json))
        return self.response, {}


class WorkerRepository:
    def __init__(self, client: RecordingClient) -> None:
        self.client = client


def test_worker_token_accepts_sha256_digest() -> None:
    token = "test-worker-token"
    settings = Settings(gpu_worker_token_hashes=hashlib.sha256(token.encode()).hexdigest())
    require_worker_token(f"Bearer {token}", settings)


def test_worker_token_rejects_invalid_value() -> None:
    settings = Settings(gpu_worker_token_hashes=hashlib.sha256(b"expected").hexdigest())
    with pytest.raises(AppError) as caught:
        require_worker_token("Bearer wrong", settings)
    assert caught.value.status_code == 401


def test_phase_c_migration_has_leases_rls_and_no_secret() -> None:
    sql = Path(
        "../supabase/migrations/202611130002_phase_c_gpu_worker_collaboration.sql"
    ).read_text(encoding="utf-8")
    assert "lease_expires_at" in sql
    assert "for update skip locked" in sql.lower()
    assert "enable row level security" in sql.lower()
    assert "grant execute on function public.claim_gpu_transcription_job" in sql.lower()
    assert "complete_gpu_transcription_job" in sql
    assert "fail_gpu_transcription_job" in sql
    assert "result_transcript_id" in sql
    assert "return job_renewed" in sql.lower()
    assert "drop constraint if exists meeting_shares_can_edit_check" not in sql.lower()
    assert "values(target_meeting_id,target_user_id,auth.uid(),false)" in sql.replace(" ", "")
    assert "on conflict(organization_id,user_id) do nothing" in sql.lower()
    assert "service_role" in sql
    assert "supabase_secret_key" not in sql.lower()
    assert sql.rstrip().endswith("commit;")


def test_whisperx_job_never_falls_back_to_local_openai() -> None:
    service = FileIngestionService(
        user_repository=None,  # type: ignore[arg-type]
        user_job_repository=None,  # type: ignore[arg-type]
        admin_repository=None,  # type: ignore[arg-type]
        admin_job_repository=None,  # type: ignore[arg-type]
        storage=None,  # type: ignore[arg-type]
        stt_provider=None,  # type: ignore[arg-type]
        user=None,  # type: ignore[arg-type]
        settings=Settings(_env_file=None),
    )
    job = JobResponse(
        id=JOB_ID,
        meeting_id=UUID("33333333-3333-4333-8333-333333333333"),
        job_type="transcribe",
        status="queued",
        attempt_count=0,
        retryable=False,
        created_at="2026-11-13T00:00:00Z",
        requested_provider="whisperx",
    )

    assert service.should_run_locally(job) is False


@pytest.mark.asyncio
async def test_worker_completion_uses_one_atomic_rpc() -> None:
    client = RecordingClient(response=str(UUID("33333333-3333-4333-8333-333333333333")))
    service = GPUWorkerService(
        WorkerRepository(client),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        Settings(_env_file=None),
    )

    await service.complete(
        JOB_ID,
        WorkerCompleteRequest(
            worker_id=WORKER_ID,
            text="안녕하세요.",
            language="ko",
            model="large-v3",
            segments=[WorkerSegment(speaker="SPEAKER_00", start=0, end=1, text="안녕하세요.")],
            usage={"segment_count": 1},
        ),
    )

    assert len(client.calls) == 1
    _, path, body = client.calls[0]
    assert path == "rpc/complete_gpu_transcription_job"
    assert body["target_worker_id"] == str(WORKER_ID)
    assert body["target_segments"][0]["speaker"] == "SPEAKER_00"


@pytest.mark.asyncio
async def test_worker_failure_rejects_expired_lease() -> None:
    client = RecordingClient(response=False)
    service = GPUWorkerService(
        WorkerRepository(client),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        Settings(_env_file=None),
    )

    with pytest.raises(AppError) as caught:
        await service.fail(JOB_ID, WORKER_ID, "WHISPERX_FAILED", "전사에 실패했습니다.")

    assert caught.value.code == "WORKER_LEASE_INVALID"
