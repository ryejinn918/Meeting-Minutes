from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.ai.analysis.base import AIProviderError, AnalysisProvider
from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.core.settings import Settings
from app.db.ai_repositories import AIRepository
from app.db.quality_repository import QualityRepository
from app.db.repositories import MeetFlowRepository
from app.schemas.jobs import JobResponse
from app.services.authorization import AuthorizationService

NON_RETRYABLE_CODES = {
    "AI_AUTHENTICATION_ERROR",
    "AI_REQUEST_REJECTED",
    "OPENROUTER_NOT_CONFIGURED",
    "OPENROUTER_MODEL_NOT_CONFIGURED",
    "TRANSCRIPT_EMPTY",
    "TRANSCRIPT_TOO_LONG",
}


class AnalysisService:
    def __init__(
        self,
        *,
        user_repository: MeetFlowRepository,
        user_ai_repository: AIRepository,
        admin_repository: MeetFlowRepository,
        admin_ai_repository: AIRepository,
        user: AuthenticatedUser,
        provider: AnalysisProvider,
        settings: Settings,
    ) -> None:
        self.user_repository = user_repository
        self.user_ai_repository = user_ai_repository
        self.admin_repository = admin_repository
        self.admin_ai_repository = admin_ai_repository
        self.user = user
        self.provider = provider
        self.settings = settings
        self.authorization = AuthorizationService(user_repository, user)

    async def start(self, meeting_id: UUID) -> JobResponse:
        meeting, transcript = await self._require_analyzable_meeting(meeting_id)
        if meeting.get("current_notes_id"):
            raise AppError(
                409,
                "REANALYSIS_REQUIRES_CONFIRMATION",
                "기존 분석 결과를 보호하기 위해 재분석은 아직 사용할 수 없습니다.",
            )
        active = await self.admin_ai_repository.get_active_job(meeting_id)
        if active:
            raise AppError(
                409,
                "ANALYSIS_ALREADY_RUNNING",
                "이미 분석 중인 회의록입니다.",
                details={"job_id": active["id"]},
            )
        if len(transcript["edited_text"]) > self.settings.ai_max_transcript_chars:
            raise AppError(
                413,
                "TRANSCRIPT_TOO_LONG",
                "회의 전문이 분석 가능한 길이를 초과했습니다. 내용을 줄인 뒤 다시 시도해 주세요.",
            )
        try:
            job = await self.admin_ai_repository.create_job(meeting_id)
        except AppError as exc:
            if exc.details and exc.details.get("upstream_code") == "23505":
                raise AppError(
                    409, "ANALYSIS_ALREADY_RUNNING", "이미 분석 중인 회의록입니다."
                ) from exc
            raise
        return self._to_response(job)

    async def get_job(self, job_id: UUID) -> JobResponse:
        job = await self.user_ai_repository.get_job(job_id)
        if job is None:
            raise AppError(404, "JOB_NOT_FOUND", "분석 작업을 찾을 수 없습니다.")
        return self._to_response(job)

    async def retry(self, job_id: UUID) -> JobResponse:
        job = await self.user_ai_repository.get_job(job_id)
        if job is None or job["job_type"] != "analyze":
            raise AppError(404, "JOB_NOT_FOUND", "분석 작업을 찾을 수 없습니다.")
        meeting = await self.user_repository.get_meeting(UUID(job["meeting_id"]))
        if meeting is None:
            raise AppError(404, "MEETING_NOT_FOUND", "회의록을 찾을 수 없습니다.")
        await self.authorization.require_meeting_manager(meeting)
        if not self._is_retryable(job):
            raise AppError(409, "JOB_NOT_RETRYABLE", "이 분석 작업은 다시 시도할 수 없습니다.")
        updated = await self.admin_ai_repository.update_job(
            job_id,
            {
                "status": "queued",
                "error_code": None,
                "error_message_safe": None,
                "started_at": None,
                "finished_at": None,
            },
        )
        return self._to_response(updated)

    async def run(self, job_id: UUID) -> None:
        job = await self.admin_ai_repository.get_job(job_id)
        if job is None:
            return
        meeting_id = UUID(job["meeting_id"])
        try:
            await self.admin_ai_repository.update_job(
                job_id,
                {
                    "status": "processing",
                    "attempt_count": int(job["attempt_count"]) + 1,
                    "started_at": datetime.now(UTC).isoformat(),
                    "finished_at": None,
                },
            )
            meeting = await self.admin_repository.get_meeting(meeting_id)
            if meeting is None or not meeting.get("current_transcript_id"):
                raise AIProviderError(
                    "TRANSCRIPT_EMPTY", "분석할 회의 전문이 없습니다.", retryable=False
                )
            if meeting.get("current_notes_id") and meeting.get("processing_status") == "ready":
                await self.admin_ai_repository.update_job(
                    job_id,
                    {
                        "status": "succeeded",
                        "error_code": None,
                        "error_message_safe": None,
                        "finished_at": datetime.now(UTC).isoformat(),
                    },
                )
                return
            transcript_id = UUID(meeting["current_transcript_id"])
            transcript = await self.admin_repository.get_transcript(transcript_id)
            text = (transcript or {}).get("edited_text", "").strip()
            if not text:
                raise AIProviderError(
                    "TRANSCRIPT_EMPTY", "분석할 회의 전문이 없습니다.", retryable=False
                )
            if len(text) > self.settings.ai_max_transcript_chars:
                raise AIProviderError(
                    "TRANSCRIPT_TOO_LONG",
                    "회의 전문이 분석 가능한 길이를 초과했습니다.",
                    retryable=False,
                )
            await self._set_meeting_status(meeting, "analyzing")
            meeting_at = datetime.fromisoformat(str(meeting["meeting_at"]).replace("Z", "+00:00"))
            client = getattr(self.admin_repository, "client", None)
            quality_repository = QualityRepository(client) if client is not None else None
            team = (
                await self.admin_repository.get_team(UUID(meeting["team_id"]))
                if quality_repository
                else None
            )
            glossary = (
                await quality_repository.list_glossary(team) if quality_repository and team else []
            )
            questions = (
                await quality_repository.list_questions(meeting_id) if quality_repository else []
            )
            template = None
            if quality_repository and meeting.get("template_id"):
                template = await quality_repository.get_template(UUID(meeting["template_id"]))
            context = {
                "topic": meeting.get("topic", ""),
                "meeting_type": meeting.get("meeting_type", "general"),
                "purpose": meeting.get("purpose", ""),
                "project_name": meeting.get("project_name", ""),
                "template": {
                    "name": template.get("name"),
                    "sections": template.get("sections", []),
                    "writing_rules": template.get("writing_rules", ""),
                }
                if template
                else None,
                "glossary": [
                    {
                        "term": item["term"],
                        "preferred_term": item["preferred_term"],
                    }
                    for item in glossary
                ],
                "confirmed_answers": [
                    {"question": item["question"], "answer": item.get("answer")}
                    for item in questions
                    if item.get("status") == "answered"
                ],
            }
            result = await self.provider.analyze(
                text, meeting_date=meeting_at.date(), context=context
            )
            output = result.analysis.model_dump(mode="json")
            usage = dict(result.usage)
            if result.request_id:
                usage["request_id"] = result.request_id
            run_id = await self.admin_ai_repository.create_ai_run(
                meeting_id=meeting_id,
                transcript_id=transcript_id,
                provider=result.provider,
                model=result.model,
                validated_output=output,
                usage=usage,
            )
            notes_id = await self.admin_ai_repository.create_notes(
                meeting_id=meeting_id,
                run_id=run_id,
                user_id=self.user.id,
                summary=result.analysis.summary,
                key_discussions=self._notes_items(result.analysis.key_discussions),
                decisions=self._notes_items(result.analysis.decisions),
                follow_ups=self._notes_items(result.analysis.follow_ups),
            )
            await self.admin_ai_repository.create_action_items(
                [
                    {
                        "id": str(uuid4()),
                        "meeting_id": str(meeting_id),
                        "source_run_id": str(run_id),
                        "description": item.description,
                        "assignee_id": None,
                        "assignee_text": item.assignee_name,
                        "due_date": item.due_date.isoformat() if item.due_date else None,
                        "status": "todo",
                        "evidence": item.evidence,
                        "sort_order": index,
                        "updated_by": str(self.user.id),
                    }
                    for index, item in enumerate(result.analysis.action_items)
                ]
            )
            latest = await self.admin_repository.get_meeting(meeting_id)
            if latest is None:
                raise AppError(404, "MEETING_NOT_FOUND", "회의록을 찾을 수 없습니다.")
            updated = await self.admin_repository.update_meeting(
                meeting_id,
                latest["version"],
                {
                    "current_notes_id": str(notes_id),
                    "processing_status": "ready",
                    "review_status": "review_required",
                },
            )
            if updated is None:
                raise AppError(409, "MEETING_VERSION_CONFLICT", "회의록 상태가 변경되었습니다.")
            await self.admin_ai_repository.update_job(
                job_id,
                {
                    "status": "succeeded",
                    "error_code": None,
                    "error_message_safe": None,
                    "finished_at": datetime.now(UTC).isoformat(),
                },
            )
        except AIProviderError as exc:
            await self._fail(job_id, meeting_id, exc.code, exc.safe_message)
        except AppError:
            await self._fail(
                job_id,
                meeting_id,
                "ANALYSIS_STORAGE_ERROR",
                "분석 결과를 저장하지 못했습니다. 다시 시도해 주세요.",
            )
        except Exception:
            await self._fail(
                job_id,
                meeting_id,
                "ANALYSIS_INTERNAL_ERROR",
                "분석 중 문제가 발생했습니다. 다시 시도해 주세요.",
            )

    async def _require_analyzable_meeting(
        self, meeting_id: UUID
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        meeting = await self.user_repository.get_meeting(meeting_id)
        if meeting is None:
            raise AppError(404, "MEETING_NOT_FOUND", "회의록을 찾을 수 없습니다.")
        await self.authorization.require_meeting_manager(meeting)
        transcript = await self.user_repository.get_transcript(
            UUID(meeting["current_transcript_id"]) if meeting.get("current_transcript_id") else None
        )
        if transcript is None or not transcript.get("edited_text", "").strip():
            raise AppError(422, "TRANSCRIPT_EMPTY", "분석할 회의 전문이 없습니다.")
        return meeting, transcript

    async def _set_meeting_status(self, meeting: dict[str, Any], status: str) -> None:
        updated = await self.admin_repository.update_meeting(
            UUID(meeting["id"]), meeting["version"], {"processing_status": status}
        )
        if updated is None:
            raise AppError(409, "MEETING_VERSION_CONFLICT", "회의록 상태가 변경되었습니다.")

    async def _fail(self, job_id: UUID, meeting_id: UUID, code: str, message: str) -> None:
        try:
            meeting = await self.admin_repository.get_meeting(meeting_id)
            if meeting:
                await self.admin_repository.update_meeting(
                    meeting_id, meeting["version"], {"processing_status": "failed"}
                )
        except AppError:
            pass
        await self.admin_ai_repository.update_job(
            job_id,
            {
                "status": "failed",
                "error_code": code,
                "error_message_safe": message,
                "finished_at": datetime.now(UTC).isoformat(),
            },
        )

    def _to_response(self, job: dict[str, Any]) -> JobResponse:
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

    def _is_retryable(self, job: dict[str, Any]) -> bool:
        if int(job.get("attempt_count", 0)) >= 2:
            return False
        if job.get("status") == "failed":
            return job.get("error_code") not in NON_RETRYABLE_CODES
        if job.get("status") == "queued" and job.get("created_at"):
            created = datetime.fromisoformat(str(job["created_at"]).replace("Z", "+00:00"))
            elapsed_seconds = (datetime.now(UTC) - created).total_seconds()
            return elapsed_seconds > self.settings.ai_stale_job_seconds
        if job.get("status") == "processing" and job.get("started_at"):
            started = datetime.fromisoformat(str(job["started_at"]).replace("Z", "+00:00"))
            elapsed_seconds = (datetime.now(UTC) - started).total_seconds()
            return elapsed_seconds > self.settings.ai_stale_job_seconds
        return False

    @staticmethod
    def _notes_items(items: list[Any]) -> list[dict[str, Any]]:
        return [
            {"id": str(uuid4()), "text": item.text, "evidence": item.evidence} for item in items
        ]
