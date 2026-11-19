import logging
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

logger = logging.getLogger("uvicorn.error")

NON_RETRYABLE_CODES = {
    "AI_AUTHENTICATION_ERROR",
    "AI_REQUEST_REJECTED",
    "OPENROUTER_NOT_CONFIGURED",
    "OPENROUTER_MODEL_NOT_CONFIGURED",
    "TRANSCRIPT_EMPTY",
    "TRANSCRIPT_TOO_LONG",
}

BUILTIN_TEMPLATE_CONTEXT: dict[str, dict[str, object]] = {
    "general": {
        "name": "기본 회의록",
        "sections": [
            {"key": "summary", "label": "회의 개요"},
            {"key": "discussions", "label": "주요 논의사항"},
            {"key": "decisions", "label": "결정사항"},
            {"key": "action_items", "label": "액션아이템"},
            {"key": "follow_up", "label": "후속 논의사항"},
        ],
        "writing_rules": "기업 실무 회의록 문체, 명사형·어구형 종결, 원문 근거 중심",
    },
    "project": {
        "name": "프로젝트 회의",
        "sections": [
            {"key": "progress", "label": "진행 현황"},
            {"key": "issues", "label": "주요 이슈"},
            {"key": "solutions", "label": "해결 방안"},
            {"key": "decisions", "label": "의사결정"},
            {"key": "action_items", "label": "담당자별 후속 조치"},
        ],
        "writing_rules": "프로젝트 진행·이슈·대안·결정·후속 조치 중심",
    },
    "interview": {
        "name": "인터뷰",
        "sections": [
            {"key": "overview", "label": "인터뷰 개요"},
            {"key": "answers", "label": "주제별 핵심 답변"},
            {"key": "qa", "label": "질의응답"},
            {"key": "insights", "label": "주요 인사이트"},
            {"key": "follow_up", "label": "후속 확인사항"},
        ],
        "writing_rules": "질문·답변의 흐름과 인터뷰이의 구체적 사례·조건·인사이트 보존",
    },
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
        stage = "load_job"
        try:
            stage = "mark_processing"
            await self.admin_ai_repository.update_job(
                job_id,
                {
                    "status": "processing",
                    "attempt_count": int(job["attempt_count"]) + 1,
                    "started_at": datetime.now(UTC).isoformat(),
                    "finished_at": None,
                },
            )
            stage = "load_meeting"
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
            stage = "load_transcript"
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
            stage = "set_analyzing_status"
            await self._set_meeting_status(meeting, "analyzing")
            meeting_at = datetime.fromisoformat(str(meeting["meeting_at"]).replace("Z", "+00:00"))
            client = getattr(self.admin_repository, "client", None)
            quality_repository = QualityRepository(client) if client is not None else None
            stage = "load_quality_context"
            team = None
            if quality_repository:
                try:
                    team = await self.admin_repository.get_team(UUID(meeting["team_id"]))
                except AppError as exc:
                    self._log_optional_context_failure("team", meeting_id, exc)
            questions: list[dict[str, Any]] = []
            template = None
            if quality_repository:
                try:
                    questions = await quality_repository.list_questions(meeting_id)
                except AppError as exc:
                    self._log_optional_context_failure("questions", meeting_id, exc)
            if quality_repository and meeting.get("template_id"):
                try:
                    template = await quality_repository.get_template(UUID(meeting["template_id"]))
                except AppError as exc:
                    self._log_optional_context_failure("template", meeting_id, exc)
            builtin_template = BUILTIN_TEMPLATE_CONTEXT.get(
                str(meeting.get("meeting_type") or "general"),
                BUILTIN_TEMPLATE_CONTEXT["general"],
            )
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
                else builtin_template,
                "correction_persona": meeting.get("correction_persona", "general"),
                "team_project_topic": (team or {}).get("project_topic", ""),
                "confirmed_answers": [
                    {"question": item["question"], "answer": item.get("answer")}
                    for item in questions
                    if item.get("status") == "answered"
                ],
            }
            team_topic = (team or {}).get("project_topic", "").strip()
            meeting_topic = meeting.get("topic", "").strip()
            correction_topic = "\n".join(
                value for value in (
                    f"팀 프로젝트 주제: {team_topic}" if team_topic else "",
                    f"이번 회의 주제: {meeting_topic}" if meeting_topic else "",
                ) if value
            )
            stage = "provider_correct_transcript"
            correction_result = None
            try:
                correction_result = await self.provider.correct_transcript(
                    text,
                    topic=correction_topic,
                    persona=meeting.get("correction_persona", "general"),
                )
            except AIProviderError as exc:
                if exc.code != "AI_INVALID_RESPONSE":
                    raise
                logger.warning(
                    "transcript_correction_fallback job_id=%s meeting_id=%s error_code=%s",
                    job_id,
                    meeting_id,
                    exc.code,
                )
            corrected_text = (
                correction_result.correction.corrected_text.strip()
                if correction_result
                else ""
            ) or text
            if quality_repository and correction_result:
                stage = "save_transcript_correction"
                await quality_repository.save_correction(
                    meeting_id=meeting_id,
                    transcript_id=transcript_id,
                    corrected_text=corrected_text,
                    changes=[
                        item.model_dump(mode="json")
                        for item in correction_result.correction.changes
                    ],
                    uncertainties=[
                        item.model_dump(mode="json")
                        for item in correction_result.correction.uncertainties
                    ],
                    context={
                        "topic": correction_topic,
                        "persona": meeting.get("correction_persona", "general"),
                    },
                    provider=correction_result.provider,
                    model=correction_result.model,
                )
            stage = "provider_analyze"
            result = await self.provider.analyze(
                corrected_text, meeting_date=meeting_at.date(), context=context
            )
            output = result.analysis.model_dump(mode="json")
            usage = dict(result.usage)
            if result.request_id:
                usage["request_id"] = result.request_id
            stage = "save_ai_run"
            run_id = await self.admin_ai_repository.create_ai_run(
                meeting_id=meeting_id,
                transcript_id=transcript_id,
                provider=result.provider,
                model=result.model,
                validated_output=output,
                usage=usage,
            )
            stage = "save_notes"
            notes_id = await self.admin_ai_repository.create_notes(
                meeting_id=meeting_id,
                run_id=run_id,
                user_id=self.user.id,
                summary=result.analysis.summary,
                key_discussions=self._notes_items(result.analysis.key_discussions),
                decisions=self._notes_items(result.analysis.decisions),
                follow_ups=self._notes_items(result.analysis.follow_ups),
            )
            stage = "save_action_items"
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
            stage = "save_meeting_result"
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
            stage = "mark_succeeded"
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
        except AppError as exc:
            details = exc.details or {}
            logger.warning(
                "analysis_failed job_id=%s meeting_id=%s stage=%s error_code=%s "
                "upstream_code=%s upstream_status=%s",
                job_id,
                meeting_id,
                stage,
                details.get("code", exc.code),
                details.get("upstream_code"),
                details.get("upstream_status"),
            )
            await self._fail(
                job_id,
                meeting_id,
                "ANALYSIS_STORAGE_ERROR",
                "분석 결과를 저장하지 못했습니다. 다시 시도해 주세요.",
            )
        except Exception as exc:
            logger.error(
                "analysis_failed job_id=%s meeting_id=%s stage=%s exception_type=%s",
                job_id,
                meeting_id,
                stage,
                type(exc).__name__,
            )
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

    @staticmethod
    def _log_optional_context_failure(kind: str, meeting_id: UUID, exc: AppError) -> None:
        details = exc.details or {}
        logger.warning(
            "optional_quality_context_unavailable kind=%s meeting_id=%s "
            "error_code=%s upstream_code=%s upstream_status=%s",
            kind,
            meeting_id,
            exc.code,
            details.get("upstream_code"),
            details.get("upstream_status"),
        )
