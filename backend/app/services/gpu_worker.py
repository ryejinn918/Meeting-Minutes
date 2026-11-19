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
        voice_profiles: list[dict[str, object]] = []
        meeting = await self.repository.get_meeting(UUID(job["meeting_id"]))
        if meeting:
            profiles, _ = await self.repository.client.request(
                "GET",
                "team_voice_profiles",
                params={
                    "select": "id,user_id,label,sample_object_path,sample_mime_type,sample_sha256",
                    "team_id": f"eq.{meeting['team_id']}",
                    "consented_at": "not.is.null",
                    "revoked_at": "is.null",
                    "sample_object_path": "not.is.null",
                },
            )
            for profile in profiles:
                sample_path = profile.get("sample_object_path")
                if not isinstance(sample_path, str) or not sample_path:
                    continue
                sample_url = await self.storage.create_signed_download(
                    self.settings.supabase_storage_bucket,
                    sample_path,
                    self.settings.gpu_worker_download_ttl_seconds,
                )
                voice_profiles.append(
                    {
                        "profile_id": profile["id"],
                        "user_id": profile["user_id"],
                        "label": profile.get("label") or "화자",
                        "download_url": sample_url,
                        "mime_type": profile.get("sample_mime_type") or "audio/mpeg",
                        "sha256": profile.get("sample_sha256"),
                    }
                )
        return WorkerJob(
            job_id=job["id"],
            meeting_id=job["meeting_id"],
            file_id=file["id"],
            download_url=url,
            original_name=file["original_name"],
            mime_type=file["mime_type"],
            voice_profiles=voice_profiles,
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
        result, _ = await self.repository.client.request(
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
        if payload.speaker_candidates and result:
            transcript_id = result if isinstance(result, str) else result.get("transcript_id")
            if transcript_id:
                transcript_rows, _ = await self.repository.client.request(
                    "GET",
                    "meeting_transcripts",
                    params={"select": "meeting_id", "id": f"eq.{transcript_id}"},
                )
                allowed_ids: set[str] = set()
                if transcript_rows:
                    meeting_row = await self.repository.get_meeting(
                        UUID(transcript_rows[0]["meeting_id"])
                    )
                    if meeting_row:
                        profile_rows, _ = await self.repository.client.request(
                            "GET", "team_voice_profiles", params={
                                "select": "user_id",
                                "team_id": f"eq.{meeting_row['team_id']}",
                                "consented_at": "not.is.null", "revoked_at": "is.null",
                                "sample_object_path": "not.is.null",
                            }
                        )
                        allowed_ids = {str(row["user_id"]) for row in profile_rows}
                speakers, _ = await self.repository.client.request(
                    "GET",
                    "transcript_speakers",
                    params={
                        "select": "id,speaker_key",
                        "transcript_id": f"eq.{transcript_id}",
                    },
                )
                by_key = {item.get("speaker_key"): item for item in speakers}
                for candidate in payload.speaker_candidates:
                    if str(candidate.candidate_user_id) not in allowed_ids:
                        continue
                    speaker = by_key.get(candidate.speaker)
                    if not speaker:
                        continue
                    profile_rows, _ = await self.repository.client.request(
                        "GET",
                        "profiles",
                        params={
                            "select": "display_name",
                            "id": f"eq.{candidate.candidate_user_id}",
                        },
                    )
                    display_name = (
                        profile_rows[0].get("display_name")
                        if profile_rows and profile_rows[0].get("display_name")
                        else candidate.speaker
                    )
                    await self.repository.client.request(
                        "PATCH",
                        "transcript_speakers",
                        params={"id": f"eq.{speaker['id']}"},
                        json={
                            "candidate_user_id": str(candidate.candidate_user_id),
                            "candidate_confidence": candidate.confidence,
                            "candidate_reason": candidate.reason,
                            "display_name": display_name,
                        },
                        prefer="return=minimal",
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
