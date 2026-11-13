from uuid import UUID

from app.core.errors import AppError
from app.core.settings import Settings
from app.db.repositories import MeetFlowRepository
from app.schemas.worker import WorkerCompleteRequest, WorkerJob
from app.services.diarization import DiarizedSegment, format_diarized_transcript, speaker_labels
from app.storage.client import SupabaseStorageClient


class GPUWorkerService:
    def __init__(
        self, repository: MeetFlowRepository, storage: SupabaseStorageClient, settings: Settings
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.settings = settings

    async def claim(self, worker_id: UUID, worker_name: str) -> WorkerJob | None:
        rows, _ = await self.repository.client.request(
            "POST",
            "rpc/claim_gpu_transcription_job",
            json={
                "target_worker_id": str(worker_id),
                "target_worker_name": worker_name,
                "lease_seconds": self.settings.gpu_worker_lease_seconds,
            },
        )
        if not rows:
            return None
        job = rows[0]
        file = await self.repository.get_meeting_file(UUID(job["file_id"]))
        if file is None:
            await self.fail(
                UUID(job["id"]), worker_id, "FILE_NOT_FOUND", "원본 파일을 찾을 수 없습니다."
            )
            return None
        url = await self.storage.create_signed_download(
            file["storage_bucket"],
            file["storage_path"],
            self.settings.gpu_worker_download_ttl_seconds,
        )
        return WorkerJob(
            job_id=job["id"],
            meeting_id=job["meeting_id"],
            file_id=file["id"],
            download_url=url,
            original_name=file["original_name"],
            mime_type=file["mime_type"],
        )

    async def heartbeat(self, job_id: UUID, worker_id: UUID) -> bool:
        value, _ = await self.repository.client.request(
            "POST",
            "rpc/heartbeat_gpu_job",
            json={
                "target_job_id": str(job_id),
                "target_worker_id": str(worker_id),
                "lease_seconds": self.settings.gpu_worker_lease_seconds,
            },
        )
        return bool(value)

    async def complete(self, job_id: UUID, payload: WorkerCompleteRequest) -> None:
        diarized = [
            DiarizedSegment(
                speaker_key=segment.speaker,
                provider_speaker=segment.speaker,
                start=segment.start,
                end=segment.end,
                text=segment.text,
            )
            for segment in payload.segments
        ]
        labels = speaker_labels(diarized)
        text = format_diarized_transcript(diarized, labels) if diarized else payload.text
        await self.repository.client.request(
            "POST",
            "rpc/complete_gpu_transcription_job",
            json={
                "target_job_id": str(job_id),
                "target_worker_id": str(payload.worker_id),
                "target_text": text,
                "target_language": payload.language,
                "target_model": payload.model,
                "target_segments": [segment.model_dump() for segment in payload.segments],
                "target_usage": payload.usage,
            },
        )

    async def fail(self, job_id: UUID, worker_id: UUID, code: str, message: str) -> None:
        value, _ = await self.repository.client.request(
            "POST",
            "rpc/fail_gpu_transcription_job",
            json={
                "target_job_id": str(job_id),
                "target_worker_id": str(worker_id),
                "target_error_code": code,
                "target_error_message": message,
            },
        )
        if not value:
            raise AppError(
                409, "WORKER_LEASE_INVALID", "작업 소유권이 만료되었거나 유효하지 않습니다."
            )
