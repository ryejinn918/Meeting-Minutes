from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.core.settings import Settings
from app.schemas.files import UploadUrlRequest
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
