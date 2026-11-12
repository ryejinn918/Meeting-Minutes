import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID, uuid4

from app.ai.stt.base import STTProvider, STTProviderError, TranscriptResult
from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.core.settings import Settings
from app.db.ai_repositories import AIRepository
from app.db.repositories import MeetFlowRepository
from app.schemas.files import (
    FileCompleteResponse,
    MeetingFileResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.schemas.jobs import JobResponse
from app.services.audio_processing import (
    merge_transcript_chunks,
    split_audio_file,
)
from app.services.authorization import AuthorizationService
from app.services.file_content import (
    extract_document_text,
    validate_file_path,
    validate_upload_metadata,
)
from app.storage.client import SupabaseStorageClient

NON_RETRYABLE_FILE_CODES = {
    "FILE_EMPTY",
    "FILE_CONTENT_INVALID",
    "FILE_SIZE_MISMATCH",
    "FILE_HASH_MISMATCH",
    "TEXT_ENCODING_INVALID",
    "PDF_ENCRYPTED",
    "PDF_DAMAGED",
    "PDF_TOO_MANY_PAGES",
    "DOCUMENT_TEXT_EMPTY",
    "STT_AUTHENTICATION_ERROR",
    "STT_REQUEST_REJECTED",
    "STT_EMPTY",
    "OPENAI_NOT_CONFIGURED",
}

INVALID_UPLOAD_OBJECT_CODES = {
    "FILE_EMPTY",
    "FILE_CONTENT_INVALID",
    "FILE_SIZE_MISMATCH",
    "FILE_HASH_MISMATCH",
    "FILE_TOO_LARGE",
}


class FileIngestionService:
    def __init__(
        self,
        *,
        user_repository: MeetFlowRepository,
        user_job_repository: AIRepository,
        admin_repository: MeetFlowRepository,
        admin_job_repository: AIRepository,
        storage: SupabaseStorageClient,
        stt_provider: STTProvider,
        user: AuthenticatedUser,
        settings: Settings,
    ) -> None:
        self.user_repository = user_repository
        self.user_job_repository = user_job_repository
        self.admin_repository = admin_repository
        self.admin_job_repository = admin_job_repository
        self.storage = storage
        self.stt_provider = stt_provider
        self.user = user
        self.settings = settings
        self.authorization = AuthorizationService(user_repository, user)

    async def create_upload_url(
        self, meeting_id: UUID, payload: UploadUrlRequest
    ) -> UploadUrlResponse:
        meeting = await self._require_manager(meeting_id)
        extension, source_type, _ = validate_upload_metadata(
            payload.filename,
            payload.content_type,
            payload.size_bytes,
            max_audio_bytes=self.settings.max_audio_bytes,
            max_document_bytes=self.settings.max_document_bytes,
        )
        meeting_source_type = meeting.get("source_type")
        if not isinstance(meeting_source_type, str):
            raise AppError(
                502,
                "MEETING_SOURCE_UNAVAILABLE",
                "회의록 입력 방식을 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.",
            )
        if meeting_source_type != source_type:
            raise AppError(
                409,
                "FILE_SOURCE_MISMATCH",
                "선택한 입력 방식과 파일 형식이 일치하지 않습니다.",
            )
        file_id = uuid4()
        storage_path = (
            f"{meeting['team_id']}/{meeting_id}/{file_id}/source{extension}"
        )
        try:
            file = await self.user_repository.create_meeting_file(
                {
                    "id": str(file_id),
                    "meeting_id": str(meeting_id),
                    "uploaded_by": str(self.user.id),
                    "storage_bucket": self.settings.supabase_storage_bucket,
                    "storage_path": storage_path,
                    "original_name": payload.filename,
                    "mime_type": payload.content_type.lower(),
                    "size_bytes": payload.size_bytes,
                    "sha256": payload.sha256,
                    "processing_status": "pending_upload",
                }
            )
        except AppError as exc:
            if exc.details and exc.details.get("upstream_code") == "23505":
                raise AppError(
                    409,
                    "FILE_ALREADY_ADDED",
                    "같은 파일이 이미 이 회의록에 추가되어 있습니다.",
                ) from exc
            raise
        try:
            signed_url, token = await self.storage.create_signed_upload(
                file["storage_bucket"], file["storage_path"]
            )
        except AppError:
            await self.user_repository.update_meeting_file(
                file_id,
                {
                    "sha256": None,
                    "processing_status": "failed",
                    "error_code": "STORAGE_SIGN_FAILED",
                },
            )
            raise
        return UploadUrlResponse(
            file=self._file_response(file),
            bucket=file["storage_bucket"],
            path=file["storage_path"],
            token=token,
            signed_url=signed_url,
        )

    async def complete(
        self, meeting_id: UUID, file_id: UUID
    ) -> FileCompleteResponse:
        meeting = await self._require_manager(meeting_id)
        file = await self.user_repository.get_meeting_file(file_id)
        if file is None or UUID(file["meeting_id"]) != meeting_id:
            raise AppError(404, "FILE_NOT_FOUND", "파일 정보를 찾을 수 없습니다.")
        if file["processing_status"] != "pending_upload":
            raise AppError(409, "FILE_ALREADY_COMPLETED", "이미 확인된 파일입니다.")
        try:
            with TemporaryDirectory(prefix="meetflow-upload-") as directory:
                source = Path(directory) / "source"
                await self.storage.download_to_path(
                    file["storage_bucket"],
                    file["storage_path"],
                    source,
                    max_bytes=int(file["size_bytes"]),
                )
                validated = await self._validate_downloaded_file(source, file)
        except AppError as exc:
            if exc.code in INVALID_UPLOAD_OBJECT_CODES:
                try:
                    await self.storage.delete(
                        file["storage_bucket"], file["storage_path"]
                    )
                except AppError:
                    pass
            await self.user_repository.update_meeting_file(
                file_id,
                {
                    "sha256": None,
                    "processing_status": "failed",
                    "error_code": exc.code,
                },
            )
            raise
        file = await self.user_repository.update_meeting_file(
            file_id,
            {
                "sha256": validated.sha256,
                "processing_status": "uploaded",
                "error_code": None,
            },
        )
        try:
            job = await self.admin_job_repository.create_job(
                meeting_id, job_type=validated.job_type, file_id=file_id
            )
        except AppError as exc:
            if exc.details and exc.details.get("upstream_code") == "23505":
                raise AppError(
                    409,
                    "FILE_PROCESSING_ALREADY_RUNNING",
                    "이미 같은 종류의 파일을 처리하고 있습니다.",
                ) from exc
            raise
        await self._set_meeting_status(meeting, "uploaded")
        return FileCompleteResponse(
            file=self._file_response(file),
            job_id=job["id"],
            job_type=job["job_type"],
        )

    async def list_files(self, meeting_id: UUID) -> list[MeetingFileResponse]:
        await self._require_visible(meeting_id)
        files = await self.user_repository.list_meeting_files(meeting_id)
        return [self._file_response(file) for file in files]

    async def get_job(self, job_id: UUID) -> JobResponse:
        job = await self.user_job_repository.get_job(job_id)
        if job is None or job["job_type"] == "analyze":
            raise AppError(404, "JOB_NOT_FOUND", "파일 처리 작업을 찾을 수 없습니다.")
        return self._job_response(job)

    async def retry(self, job_id: UUID) -> JobResponse:
        job = await self.user_job_repository.get_job(job_id)
        if job is None or job["job_type"] == "analyze":
            raise AppError(404, "JOB_NOT_FOUND", "파일 처리 작업을 찾을 수 없습니다.")
        meeting = await self._require_manager(UUID(job["meeting_id"]))
        if not self._is_retryable(job):
            raise AppError(409, "JOB_NOT_RETRYABLE", "이 파일 처리 작업은 다시 시도할 수 없습니다.")
        if not job.get("file_id"):
            raise AppError(409, "JOB_FILE_MISSING", "처리할 파일 정보를 찾을 수 없습니다.")
        await self.user_repository.update_meeting_file(
            UUID(job["file_id"]), {"processing_status": "uploaded", "error_code": None}
        )
        updated = await self.admin_job_repository.update_job(
            job_id,
            {
                "status": "queued",
                "error_code": None,
                "error_message_safe": None,
                "started_at": None,
                "finished_at": None,
            },
        )
        await self._set_meeting_status(meeting, "uploaded")
        return self._job_response(updated)

    async def run(self, job_id: UUID) -> None:
        job = await self.admin_job_repository.get_job(job_id)
        if job is None or job["job_type"] == "analyze" or not job.get("file_id"):
            return
        meeting_id = UUID(job["meeting_id"])
        file_id = UUID(job["file_id"])
        try:
            await self.admin_job_repository.update_job(
                job_id,
                {
                    "status": "processing",
                    "attempt_count": int(job["attempt_count"]) + 1,
                    "started_at": datetime.now(UTC).isoformat(),
                    "finished_at": None,
                },
            )
            file = await self.admin_repository.get_meeting_file(file_id)
            meeting = await self.admin_repository.get_meeting(meeting_id)
            if file is None or meeting is None:
                raise AppError(404, "FILE_NOT_FOUND", "처리할 파일을 찾을 수 없습니다.")
            await self.admin_repository.update_meeting_file(
                file_id, {"processing_status": "processing", "error_code": None}
            )
            await self._set_meeting_status(
                meeting, "transcribing" if job["job_type"] == "transcribe" else "uploaded"
            )
            with TemporaryDirectory(prefix=f"meetflow-job-{job_id}-") as directory:
                temp_dir = Path(directory)
                source = temp_dir / f"source{Path(file['original_name']).suffix.lower()}"
                await self.storage.download_to_path(
                    file["storage_bucket"],
                    file["storage_path"],
                    source,
                    max_bytes=int(file["size_bytes"]),
                )
                validated = await self._validate_downloaded_file(source, file)
                usage: dict[str, Any] = {
                    "source_size_bytes": int(file["size_bytes"]),
                }
                if job["job_type"] == "transcribe":
                    result, stt_usage = await self._transcribe_audio(
                        job_id, source, file, temp_dir
                    )
                    text = result.text
                    language = result.language
                    provider = result.provider
                    model = result.model
                    usage.update(stt_usage)
                else:
                    content = await asyncio.to_thread(source.read_bytes)
                    text = extract_document_text(
                        content,
                        validated.extension,
                        max_pdf_pages=self.settings.max_pdf_pages,
                    )
                    language = None
                    provider = None
                    model = None
            transcript = await self.admin_repository.create_generated_transcript(
                meeting_id=meeting_id,
                user_id=UUID(file["uploaded_by"]),
                source=validated.source_type,
                text=text,
                language=language,
                stt_provider=provider,
                stt_model=model,
            )
            latest = await self.admin_repository.get_meeting(meeting_id)
            if latest is None:
                raise AppError(404, "MEETING_NOT_FOUND", "회의록을 찾을 수 없습니다.")
            updated = await self.admin_repository.update_meeting(
                meeting_id,
                latest["version"],
                {"current_transcript_id": transcript["id"], "processing_status": "draft"},
            )
            if updated is None:
                raise AppError(409, "MEETING_VERSION_CONFLICT", "회의록 상태가 변경되었습니다.")
            await self.admin_repository.update_meeting_file(
                file_id, {"processing_status": "succeeded", "error_code": None}
            )
            await self.admin_job_repository.update_job(
                job_id,
                {
                    "status": "succeeded",
                    "usage": usage,
                    "error_code": None,
                    "error_message_safe": None,
                    "finished_at": datetime.now(UTC).isoformat(),
                },
            )
        except STTProviderError as exc:
            await self._fail(job_id, meeting_id, file_id, exc.code, exc.safe_message)
        except AppError as exc:
            await self._fail(job_id, meeting_id, file_id, exc.code, exc.message)
        except Exception:
            await self._fail(
                job_id,
                meeting_id,
                file_id,
                "FILE_PROCESSING_INTERNAL_ERROR",
                "파일을 처리하지 못했어요. 다시 시도해 주세요.",
            )

    async def _require_visible(self, meeting_id: UUID) -> dict[str, Any]:
        meeting = await self.user_repository.get_meeting(meeting_id)
        if meeting is None:
            raise AppError(404, "MEETING_NOT_FOUND", "회의록을 찾을 수 없습니다.")
        await self.authorization.require_team_member(UUID(meeting["team_id"]))
        return meeting

    async def _require_manager(self, meeting_id: UUID) -> dict[str, Any]:
        meeting = await self._require_visible(meeting_id)
        await self.authorization.require_meeting_manager(meeting)
        return meeting

    async def _set_meeting_status(self, meeting: dict[str, Any], status: str) -> None:
        updated = await self.admin_repository.update_meeting(
            UUID(meeting["id"]), meeting["version"], {"processing_status": status}
        )
        if updated is None:
            raise AppError(409, "MEETING_VERSION_CONFLICT", "회의록 상태가 변경되었습니다.")

    async def _fail(
        self, job_id: UUID, meeting_id: UUID, file_id: UUID, code: str, message: str
    ) -> None:
        try:
            file = await self.admin_repository.get_meeting_file(file_id)
            if file:
                await self.admin_repository.update_meeting_file(
                    file_id, {"processing_status": "failed", "error_code": code}
                )
            meeting = await self.admin_repository.get_meeting(meeting_id)
            if meeting:
                await self._set_meeting_status(meeting, "failed")
        except AppError:
            pass
        await self.admin_job_repository.update_job(
            job_id,
            {
                "status": "failed",
                "error_code": code,
                "error_message_safe": message,
                "finished_at": datetime.now(UTC).isoformat(),
            },
        )

    def _is_retryable(self, job: dict[str, Any]) -> bool:
        if int(job.get("attempt_count", 0)) >= 2:
            return False
        if job.get("status") == "failed":
            return job.get("error_code") not in NON_RETRYABLE_FILE_CODES
        if job.get("status") == "queued" and job.get("created_at"):
            created = datetime.fromisoformat(str(job["created_at"]).replace("Z", "+00:00"))
            elapsed = (datetime.now(UTC) - created).total_seconds()
            return elapsed > self.settings.ai_stale_job_seconds
        if job.get("status") == "processing" and job.get("started_at"):
            started = datetime.fromisoformat(str(job["started_at"]).replace("Z", "+00:00"))
            elapsed = (datetime.now(UTC) - started).total_seconds()
            return elapsed > self.settings.ai_stale_job_seconds
        return False

    async def _validate_downloaded_file(
        self, source: Path, file: dict[str, Any]
    ) -> Any:
        return await asyncio.to_thread(
            validate_file_path,
            source,
            filename=file["original_name"],
            claimed_mime=file["mime_type"],
            expected_size=int(file["size_bytes"]),
            expected_sha256=file["sha256"],
            max_audio_bytes=self.settings.max_audio_bytes,
            max_document_bytes=self.settings.max_document_bytes,
        )

    async def _transcribe_audio(
        self,
        job_id: UUID,
        source: Path,
        file: dict[str, Any],
        temp_dir: Path,
    ) -> tuple[TranscriptResult, dict[str, Any]]:
        source_size = source.stat().st_size
        if source_size <= self.settings.stt_direct_max_bytes:
            content = await asyncio.to_thread(source.read_bytes)
            result = await self.stt_provider.transcribe(
                content,
                filename=file["original_name"],
                content_type=file["mime_type"],
            )
            usage = {
                "chunk_count": 1,
                "processed_audio_bytes": len(content),
                "provider_usage": [result.usage],
            }
            return result, usage

        split = await split_audio_file(
            source,
            temp_dir,
            chunk_seconds=self.settings.stt_chunk_seconds,
            overlap_seconds=self.settings.stt_chunk_overlap_seconds,
            max_chunks=self.settings.stt_max_chunks,
            max_audio_seconds=self.settings.stt_max_audio_seconds,
            max_chunk_bytes=self.settings.stt_direct_max_bytes,
        )
        cached_rows = await self.admin_job_repository.list_job_chunks(job_id)
        cached = {int(row["chunk_index"]): row for row in cached_rows}
        texts: list[str] = []
        provider_usage: list[dict[str, Any]] = []
        processed_bytes = 0
        provider = "openai"
        model = self.settings.openai_stt_model
        for chunk in split.chunks:
            chunk_hash = await asyncio.to_thread(self._sha256_file, chunk.path)
            previous = cached.get(chunk.index)
            if previous and previous.get("chunk_sha256") == chunk_hash:
                texts.append(str(previous["transcript_text"]))
                provider_usage.append(
                    previous["usage"] if isinstance(previous.get("usage"), dict) else {}
                )
                provider = str(previous["provider"])
                model = str(previous["model"])
                processed_bytes += chunk.path.stat().st_size
                continue
            content = await asyncio.to_thread(chunk.path.read_bytes)
            result = await self.stt_provider.transcribe(
                content,
                filename=chunk.path.name,
                content_type="audio/mpeg",
            )
            chunk_usage = dict(result.usage)
            if result.request_id:
                chunk_usage["request_id"] = result.request_id
            await self.admin_job_repository.save_job_chunk(
                job_id=job_id,
                chunk_index=chunk.index,
                chunk_sha256=chunk_hash,
                start_seconds=chunk.start_seconds,
                end_seconds=chunk.end_seconds,
                transcript_text=result.text,
                provider=result.provider,
                model=result.model,
                usage=chunk_usage,
            )
            texts.append(result.text)
            provider_usage.append(chunk_usage)
            provider = result.provider
            model = result.model
            processed_bytes += len(content)
        merged = merge_transcript_chunks(texts)
        if not merged:
            raise STTProviderError(
                "STT_EMPTY",
                "음성에서 회의 내용을 찾지 못했습니다.",
                retryable=False,
            )
        return (
            TranscriptResult(
                text=merged,
                provider=provider,
                model=model,
                language="ko",
                usage={"chunks": provider_usage},
            ),
            {
                "chunk_count": len(split.chunks),
                "processed_audio_bytes": processed_bytes,
                "audio_duration_seconds": round(split.duration_seconds, 3),
                "provider_usage": provider_usage,
            },
        )

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _file_response(file: dict[str, Any]) -> MeetingFileResponse:
        return MeetingFileResponse(
            id=file["id"],
            meeting_id=file["meeting_id"],
            original_name=file["original_name"],
            mime_type=file["mime_type"],
            size_bytes=file["size_bytes"],
            processing_status=file["processing_status"],
            error_code=file.get("error_code"),
            created_at=file["created_at"],
        )

    def _job_response(self, job: dict[str, Any]) -> JobResponse:
        return JobResponse(
            id=job["id"],
            meeting_id=job["meeting_id"],
            job_type=job["job_type"],
            status=job["status"],
            attempt_count=job["attempt_count"],
            error_code=job.get("error_code"),
            error_message=job.get("error_message_safe"),
            retryable=self._is_retryable(job),
            started_at=job.get("started_at"),
            finished_at=job.get("finished_at"),
            created_at=job["created_at"],
        )
