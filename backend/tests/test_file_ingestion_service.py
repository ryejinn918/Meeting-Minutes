import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.ai.stt.base import TranscriptResult
from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.core.settings import Settings
from app.schemas.files import UploadUrlRequest
from app.services.audio_processing import AudioChunk, AudioSplitResult
from app.services.file_ingestion import FileIngestionService

USER_ID = UUID("11111111-1111-4111-8111-111111111111")
TEAM_ID = UUID("22222222-2222-4222-8222-222222222222")
MEETING_ID = UUID("33333333-3333-4333-8333-333333333333")


class FileRepository:
    def __init__(self, *, created_by: UUID = USER_ID) -> None:
        self.meeting = {
            "id": str(MEETING_ID),
            "team_id": str(TEAM_ID),
            "created_by": str(created_by),
            "source_type": "audio",
        }
        self.updated: dict[str, Any] | None = None

    async def get_meeting(self, meeting_id: UUID) -> dict[str, Any] | None:
        assert meeting_id == MEETING_ID
        return self.meeting

    async def get_membership(self, team_id: UUID, user_id: UUID) -> dict[str, Any]:
        assert team_id == TEAM_ID
        assert user_id == USER_ID
        return {"role": "member"}

    async def create_meeting_file(self, values: dict[str, Any]) -> dict[str, Any]:
        return {**values, "created_at": datetime.now(UTC).isoformat()}

    async def update_meeting_file(
        self, file_id: UUID, values: dict[str, Any]
    ) -> dict[str, Any]:
        self.updated = values
        return {"id": str(file_id), **values}


class FailingStorage:
    async def create_signed_upload(self, bucket: str, path: str) -> tuple[str, str]:
        raise AppError(502, "STORAGE_ERROR", "저장소 오류")


class SuccessfulStorage:
    async def create_signed_upload(self, bucket: str, path: str) -> tuple[str, str]:
        assert bucket == "meeting-files"
        assert "original-name" not in path
        return "https://example.invalid/upload?token=signed", "signed"


class CompleteRepository(FileRepository):
    async def get_meeting_file(self, file_id: UUID) -> dict[str, Any]:
        return {
            "id": str(file_id),
            "meeting_id": str(MEETING_ID),
            "uploaded_by": str(USER_ID),
            "storage_bucket": "meeting-files",
            "storage_path": f"{TEAM_ID}/{MEETING_ID}/{file_id}/source.mp3",
            "original_name": "meeting.mp3",
            "mime_type": "audio/mpeg",
            "size_bytes": 128,
            "sha256": "a" * 64,
            "processing_status": "pending_upload",
        }


class TransientDownloadStorage:
    deleted = False

    async def download_to_path(
        self, bucket: str, path: str, destination: Path, *, max_bytes: int
    ) -> None:
        raise AppError(502, "STORAGE_UNAVAILABLE", "저장소에 연결하지 못했습니다.")

    async def delete(self, bucket: str, path: str) -> None:
        self.deleted = True


def service(repository: FileRepository, storage: object) -> FileIngestionService:
    user = AuthenticatedUser(id=USER_ID, email=None, access_token="token")
    return FileIngestionService(
        user_repository=repository,  # type: ignore[arg-type]
        user_job_repository=None,  # type: ignore[arg-type]
        admin_repository=repository,  # type: ignore[arg-type]
        admin_job_repository=None,  # type: ignore[arg-type]
        storage=storage,  # type: ignore[arg-type]
        stt_provider=None,  # type: ignore[arg-type]
        user=user,
        settings=Settings(_env_file=None),
    )


def upload_payload() -> UploadUrlRequest:
    return UploadUrlRequest(
        filename="original-name.mp3",
        content_type="audio/mpeg",
        size_bytes=128,
        sha256="a" * 64,
    )


@pytest.mark.asyncio
async def test_signed_upload_path_uses_uuid_not_original_filename() -> None:
    result = await service(FileRepository(), SuccessfulStorage()).create_upload_url(
        MEETING_ID, upload_payload()
    )

    assert result.file.original_name == "original-name.mp3"
    assert result.path.endswith("/source.mp3")
    assert "original-name" not in result.path


@pytest.mark.asyncio
async def test_storage_sign_failure_releases_duplicate_hash_for_retry() -> None:
    repository = FileRepository()

    with pytest.raises(AppError) as error:
        await service(repository, FailingStorage()).create_upload_url(
            MEETING_ID, upload_payload()
        )

    assert error.value.code == "STORAGE_ERROR"
    assert repository.updated == {
        "sha256": None,
        "processing_status": "failed",
        "error_code": "STORAGE_SIGN_FAILED",
    }


@pytest.mark.asyncio
async def test_transient_complete_failure_preserves_original_storage_object() -> None:
    repository = CompleteRepository()
    storage = TransientDownloadStorage()

    with pytest.raises(AppError) as error:
        await service(repository, storage).complete(MEETING_ID, uuid4())

    assert error.value.code == "STORAGE_UNAVAILABLE"
    assert storage.deleted is False


@pytest.mark.asyncio
async def test_read_only_team_member_cannot_upload_to_another_users_meeting() -> None:
    repository = FileRepository(created_by=UUID("44444444-4444-4444-8444-444444444444"))

    with pytest.raises(AppError) as error:
        await service(repository, SuccessfulStorage()).create_upload_url(
            MEETING_ID, upload_payload()
        )

    assert error.value.code == "MEETING_EDIT_DENIED"


def test_stale_queued_file_job_can_be_retried() -> None:
    file_service = service(FileRepository(), SuccessfulStorage())
    job = {
        "status": "queued",
        "attempt_count": 0,
        "created_at": (datetime.now(UTC) - timedelta(minutes=10)).isoformat(),
    }

    assert file_service._is_retryable(job) is True


@pytest.mark.asyncio
async def test_large_audio_retry_reuses_completed_chunk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.wav"
    source.write_bytes(b"source-audio")
    first = tmp_path / "chunk-000.mp3"
    second = tmp_path / "chunk-001.mp3"
    first.write_bytes(b"first-chunk")
    second.write_bytes(b"second-chunk")
    first_hash = hashlib.sha256(first.read_bytes()).hexdigest()

    async def fake_split(*args: Any, **kwargs: Any) -> AudioSplitResult:
        return AudioSplitResult(
            chunks=[
                AudioChunk(0, first, 0, 602),
                AudioChunk(1, second, 600, 900),
            ],
            duration_seconds=900,
        )

    class ChunkRepository:
        saved: list[dict[str, Any]] = []

        async def list_job_chunks(self, job_id: UUID) -> list[dict[str, Any]]:
            return [
                {
                    "chunk_index": 0,
                    "chunk_sha256": first_hash,
                    "transcript_text": "첫 구간의 마지막 세 단어",
                    "provider": "openai",
                    "model": "gpt-transcribe",
                    "usage": {"input_tokens": 1},
                }
            ]

        async def save_job_chunk(self, **values: Any) -> None:
            self.saved.append(values)

    class CountingProvider:
        calls = 0

        async def transcribe(
            self, content: bytes, *, filename: str, content_type: str
        ) -> TranscriptResult:
            self.calls += 1
            assert content == b"second-chunk"
            return TranscriptResult(
                text="마지막 세 단어 다음 구간입니다",
                provider="openai",
                model="gpt-transcribe",
                language="ko",
            )

    monkeypatch.setattr("app.services.file_ingestion.split_audio_file", fake_split)
    chunk_repository = ChunkRepository()
    provider = CountingProvider()
    ingestion = FileIngestionService(
        user_repository=FileRepository(),  # type: ignore[arg-type]
        user_job_repository=chunk_repository,  # type: ignore[arg-type]
        admin_repository=FileRepository(),  # type: ignore[arg-type]
        admin_job_repository=chunk_repository,  # type: ignore[arg-type]
        storage=SuccessfulStorage(),  # type: ignore[arg-type]
        stt_provider=provider,
        user=AuthenticatedUser(id=USER_ID, email=None, access_token="token"),
        settings=Settings(_env_file=None, stt_direct_max_bytes=1),
    )

    result, usage = await ingestion._transcribe_audio(
        uuid4(),
        source,
        {"original_name": "meeting.wav", "mime_type": "audio/wav"},
        tmp_path,
    )

    assert provider.calls == 1
    assert [saved["chunk_index"] for saved in chunk_repository.saved] == [1]
    assert result.text == "첫 구간의 마지막 세 단어 다음 구간입니다"
    assert usage["chunk_count"] == 2
