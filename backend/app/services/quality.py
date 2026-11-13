from typing import Any
from uuid import UUID

from app.ai.analysis.base import AIProviderError, AnalysisProvider
from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.db.quality_repository import QualityRepository
from app.db.repositories import MeetFlowRepository
from app.schemas.quality import (
    GlossaryTermCreate,
    GlossaryTermResponse,
    GlossaryTermUpdate,
    MeetingTemplateCreate,
    MeetingTemplateResponse,
    MeetingTemplateUpdate,
    QualityOptionsResponse,
    QuestionAnswer,
    QuestionCreate,
    QuestionResponse,
    SegmentSpeakerUpdate,
    SpeakerEditResponse,
    TranscriptCorrectionResult,
)
from app.services.authorization import AuthorizationService

BUILTIN_TEMPLATES = [
    {
        "id": "builtin-general",
        "name": "일반 회의",
        "description": "논의, 결정, 액션아이템을 균형 있게 정리합니다.",
        "meeting_type": "general",
        "sections": [
            {"key": "summary", "label": "회의 개요"},
            {"key": "discussions", "label": "주요 논의사항"},
            {"key": "decisions", "label": "결정사항"},
            {"key": "action_items", "label": "액션아이템"},
            {"key": "follow_up", "label": "다음 회의"},
        ],
    },
    {
        "id": "builtin-project",
        "name": "프로젝트 회의",
        "description": "진행 현황과 이슈, 후속 조치를 중심으로 정리합니다.",
        "meeting_type": "project",
        "sections": [
            {"key": "progress", "label": "진행 현황"},
            {"key": "issues", "label": "주요 이슈"},
            {"key": "solutions", "label": "해결 방안"},
            {"key": "decisions", "label": "의사결정"},
            {"key": "action_items", "label": "담당자별 후속 조치"},
        ],
    },
    {
        "id": "builtin-interview",
        "name": "인터뷰",
        "description": "질의응답과 핵심 인사이트를 중심으로 정리합니다.",
        "meeting_type": "interview",
        "sections": [
            {"key": "overview", "label": "인터뷰 개요"},
            {"key": "answers", "label": "주제별 핵심 답변"},
            {"key": "qa", "label": "질의응답"},
            {"key": "insights", "label": "주요 인사이트"},
            {"key": "follow_up", "label": "후속 확인사항"},
        ],
    },
    {
        "id": "builtin-workshop",
        "name": "워크숍·아이디어 회의",
        "description": "아이디어와 검토 의견, 향후 과제를 정리합니다.",
        "meeting_type": "workshop",
        "sections": [
            {"key": "purpose", "label": "회의 목적"},
            {"key": "ideas", "label": "제안 아이디어"},
            {"key": "feedback", "label": "검토 의견"},
            {"key": "agreements", "label": "합의 내용"},
            {"key": "action_items", "label": "향후 과제"},
        ],
    },
]


class QualityService:
    def __init__(
        self,
        repository: MeetFlowRepository,
        user: AuthenticatedUser,
        provider: AnalysisProvider,
    ) -> None:
        self.repository = repository
        self.quality = QualityRepository(repository.client)
        self.user = user
        self.provider = provider
        self.authorization = AuthorizationService(repository, user)

    async def options(self, team_id: UUID) -> QualityOptionsResponse:
        await self.authorization.require_team_member(team_id)
        team = await self._team(team_id)
        custom, glossary = await self._templates_and_glossary(team)
        builtins = [self._builtin_response(item) for item in BUILTIN_TEMPLATES]
        return QualityOptionsResponse(
            templates=[*builtins, *[MeetingTemplateResponse(**item) for item in custom]],
            glossary_terms=[GlossaryTermResponse(**item) for item in glossary],
        )

    async def create_template(self, payload: MeetingTemplateCreate) -> MeetingTemplateResponse:
        await self._require_scope_manager(payload.model_dump())
        row = await self.quality.create_template(
            {
                **payload.model_dump(mode="json"),
                "created_by": str(self.user.id),
            }
        )
        return MeetingTemplateResponse(**row)

    async def update_template(
        self, template_id: UUID, payload: MeetingTemplateUpdate
    ) -> MeetingTemplateResponse:
        current = await self.quality.get_template(template_id)
        if current is None:
            raise AppError(404, "TEMPLATE_NOT_FOUND", "템플릿을 찾을 수 없습니다.")
        await self._require_scope_manager(current)
        updated = await self.quality.update_template(
            template_id, payload.model_dump(exclude_none=True, mode="json")
        )
        if updated is None:
            raise AppError(404, "TEMPLATE_NOT_FOUND", "템플릿을 찾을 수 없습니다.")
        return MeetingTemplateResponse(**updated)

    async def delete_template(self, template_id: UUID) -> None:
        current = await self.quality.get_template(template_id)
        if current is None:
            raise AppError(404, "TEMPLATE_NOT_FOUND", "템플릿을 찾을 수 없습니다.")
        await self._require_scope_manager(current)
        await self.quality.delete_template(template_id)

    async def create_glossary(self, payload: GlossaryTermCreate) -> GlossaryTermResponse:
        await self._require_scope_manager(payload.model_dump())
        row = await self.quality.create_glossary_term(
            {**payload.model_dump(mode="json"), "created_by": str(self.user.id)}
        )
        return GlossaryTermResponse(**row)

    async def update_glossary(
        self, term_id: UUID, payload: GlossaryTermUpdate
    ) -> GlossaryTermResponse:
        current = await self.quality.get_glossary_term(term_id)
        if current is None:
            raise AppError(404, "GLOSSARY_TERM_NOT_FOUND", "전문 용어를 찾을 수 없습니다.")
        await self._require_scope_manager(current)
        values = payload.model_dump(exclude_none=True)
        if "aliases" in values:
            values["aliases"] = [item.strip() for item in values["aliases"] if item.strip()]
        updated = await self.quality.update_glossary_term(term_id, values)
        if updated is None:
            raise AppError(404, "GLOSSARY_TERM_NOT_FOUND", "전문 용어를 찾을 수 없습니다.")
        return GlossaryTermResponse(**updated)

    async def delete_glossary(self, term_id: UUID) -> None:
        current = await self.quality.get_glossary_term(term_id)
        if current is None:
            raise AppError(404, "GLOSSARY_TERM_NOT_FOUND", "전문 용어를 찾을 수 없습니다.")
        await self._require_scope_manager(current)
        await self.quality.delete_glossary_term(term_id)

    async def correct_transcript(self, meeting_id: UUID) -> TranscriptCorrectionResult:
        meeting = await self._managed_meeting(meeting_id)
        transcript_id = meeting.get("current_transcript_id")
        transcript = await self.repository.get_transcript(
            UUID(transcript_id) if transcript_id else None
        )
        text = (transcript or {}).get("edited_text", "").strip()
        if not transcript or not text:
            raise AppError(422, "TRANSCRIPT_EMPTY", "교정할 회의 전문이 없습니다.")
        team = await self._team(UUID(meeting["team_id"]))
        glossary = await self.quality.list_glossary(team)
        try:
            result = await self.provider.correct_transcript(
                text, topic=meeting.get("topic", ""), glossary=glossary
            )
        except AIProviderError as exc:
            raise AppError(502, exc.code, exc.safe_message) from exc
        correction = result.correction
        await self.quality.save_correction(
            meeting_id=meeting_id,
            transcript_id=UUID(transcript["id"]),
            corrected_text=correction.corrected_text,
            changes=[item.model_dump(mode="json") for item in correction.changes],
            uncertainties=[item.model_dump(mode="json") for item in correction.uncertainties],
            context={
                "topic": meeting.get("topic", ""),
                "glossary_term_ids": [item["id"] for item in glossary],
            },
            provider=result.provider,
            model=result.model,
        )
        return correction

    async def create_question(self, meeting_id: UUID, payload: QuestionCreate) -> QuestionResponse:
        await self._managed_meeting(meeting_id)
        row = await self.quality.create_question(
            {
                "meeting_id": str(meeting_id),
                **payload.model_dump(mode="json"),
                "created_by": str(self.user.id),
            }
        )
        return QuestionResponse(**row)

    async def answer_question(
        self, meeting_id: UUID, question_id: UUID, payload: QuestionAnswer
    ) -> QuestionResponse:
        await self._managed_meeting(meeting_id)
        row = await self.quality.answer_question(
            meeting_id, question_id, self.user.id, payload.answer, payload.status
        )
        if row is None:
            raise AppError(404, "QUESTION_NOT_FOUND", "확인 질문을 찾을 수 없습니다.")
        return QuestionResponse(**row)

    async def edit_segment_speaker(
        self, meeting_id: UUID, segment_id: UUID, payload: SegmentSpeakerUpdate
    ) -> SpeakerEditResponse:
        await self._managed_meeting(meeting_id)
        batch_id = await self.quality.apply_speaker_edit(
            meeting_id, segment_id, payload.speaker_id, payload.scope
        )
        batch = await self.quality.get_speaker_edit_batch(batch_id)
        changed_count = len((batch or {}).get("changes", []))
        return SpeakerEditResponse(batch_id=batch_id, changed_count=changed_count)

    async def undo_speaker_edit(self, meeting_id: UUID, batch_id: UUID) -> SpeakerEditResponse:
        await self._managed_meeting(meeting_id)
        batch = await self.quality.get_speaker_edit_batch(batch_id)
        if batch is None or batch.get("meeting_id") != str(meeting_id):
            raise AppError(404, "SPEAKER_EDIT_NOT_FOUND", "되돌릴 화자 변경을 찾을 수 없습니다.")
        changed = await self.quality.undo_speaker_edit(batch_id)
        return SpeakerEditResponse(batch_id=batch_id, changed_count=changed)

    async def _managed_meeting(self, meeting_id: UUID) -> dict[str, Any]:
        meeting = await self.repository.get_meeting(meeting_id)
        if meeting is None:
            raise AppError(404, "MEETING_NOT_FOUND", "회의록을 찾을 수 없습니다.")
        await self.authorization.require_meeting_manager(meeting)
        return meeting

    async def _team(self, team_id: UUID) -> dict[str, Any]:
        team = await self.repository.get_team(team_id)
        if team is None:
            raise AppError(404, "TEAM_NOT_FOUND", "팀을 찾을 수 없습니다.")
        return team

    async def _templates_and_glossary(
        self, team: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        import asyncio

        return await asyncio.gather(
            self.quality.list_templates(team), self.quality.list_glossary(team)
        )

    async def _require_scope_manager(self, values: dict[str, Any]) -> None:
        team_id = values.get("team_id")
        department_id = values.get("department_id")
        organization_id = values.get("organization_id")
        if team_id:
            membership = await self.authorization.require_team_member(UUID(str(team_id)))
            if membership["role"] not in {"owner", "admin"}:
                raise AppError(403, "QUALITY_SCOPE_ADMIN_REQUIRED", "팀 관리자 권한이 필요합니다.")
            return
        if department_id:
            membership = await self.repository.get_department_membership(
                UUID(str(department_id)), self.user.id
            )
            if membership and membership["role"] == "department_admin":
                return
        if organization_id:
            await self.authorization.require_organization_admin(UUID(str(organization_id)))
            return
        raise AppError(403, "QUALITY_SCOPE_ADMIN_REQUIRED", "관리자 권한이 필요합니다.")

    @staticmethod
    def _builtin_response(item: dict[str, Any]) -> MeetingTemplateResponse:
        return MeetingTemplateResponse(
            **item,
            organization_id=None,
            department_id=None,
            team_id=None,
            writing_rules="",
            is_default=True,
            version=1,
            is_active=True,
            is_builtin=True,
            created_at=None,
        )
