from datetime import UTC, datetime
from uuid import UUID

from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.db.repositories import MeetFlowRepository
from app.schemas.meetings import (
    ActionItemResponse,
    MeetingCreate,
    MeetingNotesUpdate,
    MeetingResponse,
    MeetingUpdate,
    UserSummary,
    normalize_items,
)
from app.services.authorization import AuthorizationService


class MeetingService:
    def __init__(self, repository: MeetFlowRepository, user: AuthenticatedUser) -> None:
        self.repository = repository
        self.user = user
        self.authorization = AuthorizationService(repository, user)

    async def create(self, payload: MeetingCreate) -> MeetingResponse:
        await self.authorization.require_team_member(payload.team_id)
        meeting = await self.repository.create_meeting(
            {
                "team_id": str(payload.team_id),
                "title": payload.title.strip(),
                "meeting_at": payload.meeting_at.isoformat(),
                "source_type": payload.source_type,
                "created_by": str(self.user.id),
                "processing_status": "draft",
            }
        )
        return await self._hydrate(meeting)

    async def list(self, team_id: UUID) -> list[MeetingResponse]:
        await self.authorization.require_team_member(team_id)
        rows = await self.repository.list_meetings(team_id)
        profiles = await self.repository.get_profiles({UUID(row["created_by"]) for row in rows})
        return [await self._hydrate(row, profiles) for row in rows]

    async def get(self, meeting_id: UUID) -> MeetingResponse:
        meeting = await self._get_visible(meeting_id)
        return await self._hydrate(meeting)

    async def update(self, meeting_id: UUID, payload: MeetingUpdate) -> MeetingResponse:
        meeting = await self._get_visible(meeting_id)
        await self.authorization.require_meeting_manager(meeting)
        if payload.version is not None and payload.version != meeting["version"]:
            raise AppError(
                409,
                "MEETING_VERSION_CONFLICT",
                "다른 변경사항이 있어 회의록을 다시 불러와야 합니다.",
            )
        values = payload.model_dump(exclude_none=True, exclude={"version"})
        if "meeting_at" in values:
            values["meeting_at"] = values["meeting_at"].isoformat()
        updated = await self.repository.update_meeting(meeting_id, meeting["version"], values)
        if updated is None:
            raise AppError(
                409,
                "MEETING_VERSION_CONFLICT",
                "다른 변경사항이 있어 회의록을 다시 불러와야 합니다.",
            )
        return await self._hydrate(updated)

    async def delete(self, meeting_id: UUID) -> None:
        meeting = await self._get_visible(meeting_id)
        await self.authorization.require_meeting_manager(meeting)
        await self.repository.soft_delete_meeting(
            meeting_id, meeting["version"], datetime.now(UTC).isoformat()
        )

    async def save_transcript(self, meeting_id: UUID, text: str) -> MeetingResponse:
        meeting = await self._get_visible(meeting_id)
        await self.authorization.require_meeting_manager(meeting)
        transcript_id = meeting.get("current_transcript_id")
        if transcript_id:
            await self.repository.update_transcript(UUID(transcript_id), text)
        else:
            transcript = await self.repository.get_latest_direct_transcript(
                meeting_id, self.user.id
            )
            if transcript:
                await self.repository.update_transcript(UUID(transcript["id"]), text)
            else:
                transcript = await self.repository.create_transcript(
                    meeting_id, self.user.id, text
                )
            updated = await self.repository.update_meeting(
                meeting_id, meeting["version"], {"current_transcript_id": transcript["id"]}
            )
            if updated is None:
                raise AppError(
                    409, "MEETING_VERSION_CONFLICT", "전문 저장 중 회의록이 변경되었습니다."
                )
        refreshed = await self._get_visible(meeting_id)
        return await self._hydrate(refreshed)

    async def update_notes(
        self, meeting_id: UUID, payload: MeetingNotesUpdate
    ) -> MeetingResponse:
        meeting = await self._get_visible(meeting_id)
        await self.authorization.require_meeting_manager(meeting)
        if not meeting.get("current_notes_id"):
            raise AppError(409, "NOTES_NOT_READY", "수정할 분석 결과가 없습니다.")
        if payload.version != meeting["version"]:
            raise AppError(
                409,
                "MEETING_VERSION_CONFLICT",
                "다른 변경사항이 있어 회의록을 다시 불러와야 합니다.",
            )
        version_update = await self.repository.update_meeting(
            meeting_id, meeting["version"], {}
        )
        if version_update is None:
            raise AppError(
                409,
                "MEETING_VERSION_CONFLICT",
                "다른 변경사항이 있어 회의록을 다시 불러와야 합니다.",
            )
        await self.repository.update_notes(
            UUID(meeting["current_notes_id"]),
            {
                "summary": payload.summary.strip(),
                "key_discussions": [
                    item.model_dump(mode="json") for item in payload.key_discussions
                ],
                "decisions": [item.model_dump(mode="json") for item in payload.decisions],
                "follow_ups": [
                    item.model_dump(mode="json") for item in payload.follow_ups
                ],
                "updated_by": str(self.user.id),
            },
        )
        return await self._hydrate(version_update)

    async def _get_visible(self, meeting_id: UUID) -> dict:
        meeting = await self.repository.get_meeting(meeting_id)
        if meeting is None:
            raise AppError(404, "MEETING_NOT_FOUND", "회의록을 찾을 수 없습니다.")
        await self.authorization.require_team_member(UUID(meeting["team_id"]))
        return meeting

    async def _hydrate(
        self, meeting: dict, profiles: dict[str, dict] | None = None
    ) -> MeetingResponse:
        creator_id = UUID(meeting["created_by"])
        profile_map = profiles or await self.repository.get_profiles({creator_id})
        profile = profile_map.get(str(creator_id))
        if profile is None:
            raise AppError(502, "PROFILE_NOT_FOUND", "회의록 작성자 정보를 찾을 수 없습니다.")
        transcript = await self.repository.get_transcript(
            UUID(meeting["current_transcript_id"]) if meeting.get("current_transcript_id") else None
        )
        notes = await self.repository.get_notes(
            UUID(meeting["current_notes_id"]) if meeting.get("current_notes_id") else None
        )
        source_run_id = (
            UUID(notes["derived_from_run_id"])
            if notes and notes.get("derived_from_run_id")
            else None
        )
        if source_run_id:
            ai_run = await self.repository.get_ai_run(source_run_id)
            actions = await self.repository.list_action_items(
                UUID(meeting["id"]), source_run_id
            )
        else:
            ai_run = None
            actions = await self.repository.list_action_items(UUID(meeting["id"]))
        shared_ids = await self.repository.list_shared_member_ids(UUID(meeting["id"]))
        meeting_fields = {key: value for key, value in meeting.items() if key != "created_by"}
        return MeetingResponse(
            **meeting_fields,
            created_by=UserSummary(
                id=profile["id"],
                name=profile["display_name"],
                email=profile["email"],
                avatar_url=profile.get("avatar_url"),
            ),
            is_mine=creator_id == self.user.id,
            is_shared_with_me=self.user.id in shared_ids,
            summary=(notes or {}).get("summary", ""),
            transcript_original=(transcript or {}).get("original_text", ""),
            transcript_edited=(transcript or {}).get("edited_text", ""),
            key_discussions=normalize_items((notes or {}).get("key_discussions")),
            decisions=normalize_items((notes or {}).get("decisions")),
            follow_ups=normalize_items((notes or {}).get("follow_ups")),
            action_items=[
                ActionItemResponse(
                    id=item["id"],
                    description=item["description"],
                    assignee_id=item.get("assignee_id"),
                    assignee_name=item.get("assignee_text"),
                    due_date=item.get("due_date"),
                    status=item["status"],
                )
                for item in actions
            ],
            shared_member_ids=shared_ids,
            ai_generated_at=(ai_run or {}).get("completed_at"),
        )
