import asyncio
from datetime import UTC, datetime
from uuid import UUID

from app.core.errors import AppError
from app.core.security import AuthenticatedUser
from app.db.quality_repository import QualityRepository
from app.db.repositories import MeetFlowRepository
from app.schemas.meetings import (
    ActionItemResponse,
    MeetingCreate,
    MeetingListItemResponse,
    MeetingNotesUpdate,
    MeetingResponse,
    MeetingUpdate,
    TranscriptSegmentResponse,
    TranscriptSpeakerResponse,
    TranscriptSpeakerUpdate,
    UserSummary,
    normalize_items,
)
from app.services.authorization import AuthorizationService


class MeetingService:
    def __init__(
        self,
        repository: MeetFlowRepository,
        user: AuthenticatedUser,
        quality_repository: QualityRepository | None = None,
    ) -> None:
        self.repository = repository
        self.user = user
        self.authorization = AuthorizationService(repository, user)
        client = getattr(repository, "client", None)
        self.quality_repository = quality_repository or (
            QualityRepository(client) if client is not None else None
        )

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
                "topic": payload.topic.strip(),
                "location": payload.location.strip(),
                "meeting_type": payload.meeting_type,
                "purpose": payload.purpose.strip(),
                "project_name": payload.project_name.strip(),
                "template_id": str(payload.template_id) if payload.template_id else None,
                "metadata_confirmed_at": datetime.now(UTC).isoformat()
                if payload.metadata_confirmed
                else None,
            }
        )
        if payload.attendees:
            if self.quality_repository is None:
                raise AppError(
                    503,
                    "QUALITY_STORAGE_UNAVAILABLE",
                    "참석자 저장소를 사용할 수 없습니다.",
                )
            await self.quality_repository.set_attendees(
                UUID(meeting["id"]),
                [item.model_dump(mode="json", exclude_none=True) for item in payload.attendees],
            )
        return await self._hydrate(meeting)

    async def list(self, team_id: UUID) -> list[MeetingListItemResponse]:
        await self.authorization.require_team_member(team_id)
        rows = await self.repository.list_meetings(team_id)
        profiles, shared_meeting_ids = await asyncio.gather(
            self.repository.get_profiles({UUID(row["created_by"]) for row in rows}),
            self.repository.list_shared_meeting_ids(
                self.user.id, {UUID(row["id"]) for row in rows}
            ),
        )
        return [self._summarize(row, profiles, shared_meeting_ids) for row in rows]

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
        attendees = payload.attendees
        values = payload.model_dump(
            exclude_none=True,
            exclude={"version", "attendees", "metadata_confirmed"},
        )
        if "meeting_at" in values:
            values["meeting_at"] = values["meeting_at"].isoformat()
        if payload.metadata_confirmed is not None:
            values["metadata_confirmed_at"] = (
                datetime.now(UTC).isoformat() if payload.metadata_confirmed else None
            )
        if "template_id" in values:
            values["template_id"] = str(values["template_id"])
        updated = await self.repository.update_meeting(meeting_id, meeting["version"], values)
        if updated is None:
            raise AppError(
                409,
                "MEETING_VERSION_CONFLICT",
                "다른 변경사항이 있어 회의록을 다시 불러와야 합니다.",
            )
        if attendees is not None:
            if self.quality_repository is None:
                raise AppError(
                    503,
                    "QUALITY_STORAGE_UNAVAILABLE",
                    "참석자 저장소를 사용할 수 없습니다.",
                )
            await self.quality_repository.set_attendees(
                meeting_id,
                [item.model_dump(mode="json", exclude_none=True) for item in attendees],
            )
        return await self._hydrate(updated)

    async def delete(self, meeting_id: UUID) -> None:
        meeting = await self._get_visible(meeting_id)
        await self.authorization.require_meeting_manager(meeting)
        result = await self.repository.soft_delete_meeting(meeting_id, meeting["version"])
        if result == "deleted":
            return
        if result == "active_job":
            raise AppError(
                409,
                "MEETING_PROCESSING_ACTIVE",
                "진행 중인 작업이 끝난 뒤 회의록을 삭제해 주세요.",
            )
        if result == "version_conflict":
            raise AppError(
                409,
                "MEETING_VERSION_CONFLICT",
                "다른 변경사항이 있어 회의록을 다시 불러와야 합니다.",
            )
        if result == "forbidden":
            raise AppError(403, "MEETING_DELETE_DENIED", "이 회의록을 삭제할 권한이 없습니다.")
        raise AppError(404, "MEETING_NOT_FOUND", "회의록을 찾을 수 없습니다.")

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
                transcript = await self.repository.create_transcript(meeting_id, self.user.id, text)
            updated = await self.repository.update_meeting(
                meeting_id, meeting["version"], {"current_transcript_id": transcript["id"]}
            )
            if updated is None:
                raise AppError(
                    409, "MEETING_VERSION_CONFLICT", "전문 저장 중 회의록이 변경되었습니다."
                )
        refreshed = await self._get_visible(meeting_id)
        return await self._hydrate(refreshed)

    async def update_notes(self, meeting_id: UUID, payload: MeetingNotesUpdate) -> MeetingResponse:
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
        version_update = await self.repository.update_meeting(meeting_id, meeting["version"], {})
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
                "follow_ups": [item.model_dump(mode="json") for item in payload.follow_ups],
                "updated_by": str(self.user.id),
            },
        )
        return await self._hydrate(version_update)

    async def update_transcript_speaker(
        self,
        meeting_id: UUID,
        speaker_id: UUID,
        payload: TranscriptSpeakerUpdate,
    ) -> MeetingResponse:
        meeting = await self._get_visible(meeting_id)
        await self.authorization.require_meeting_manager(meeting)
        transcript_id = (
            UUID(meeting["current_transcript_id"]) if meeting.get("current_transcript_id") else None
        )
        speakers = await self.repository.list_transcript_speakers(transcript_id)
        speaker = next(
            (item for item in speakers if UUID(item["id"]) == speaker_id),
            None,
        )
        if speaker is None:
            raise AppError(404, "TRANSCRIPT_SPEAKER_NOT_FOUND", "화자 정보를 찾을 수 없습니다.")
        display_name = payload.display_name.strip()
        await self.repository.update_transcript_speaker(speaker_id, display_name)
        transcript = await self.repository.get_transcript(transcript_id)
        if transcript and isinstance(transcript.get("edited_text"), str):
            old_prefix = f"] {speaker['display_name']}: "
            new_prefix = f"] {display_name}: "
            edited_text = transcript["edited_text"].replace(old_prefix, new_prefix)
            if edited_text != transcript["edited_text"]:
                await self.repository.update_transcript(transcript_id, edited_text)
        return await self._hydrate(meeting)

    async def _get_visible(self, meeting_id: UUID) -> dict:
        meeting = await self.repository.get_meeting(meeting_id)
        if meeting is None:
            raise AppError(404, "MEETING_NOT_FOUND", "회의록을 찾을 수 없습니다.")
        await self.authorization.require_team_member(UUID(meeting["team_id"]))
        return meeting

    async def _hydrate(self, meeting: dict) -> MeetingResponse:
        creator_id = UUID(meeting["created_by"])
        transcript_id = (
            UUID(meeting["current_transcript_id"]) if meeting.get("current_transcript_id") else None
        )
        notes_id = UUID(meeting["current_notes_id"]) if meeting.get("current_notes_id") else None
        (
            profile_map,
            transcript,
            speakers,
            segments,
            notes,
            shared_ids,
            attendees,
            questions,
            speaker_edits,
            latest_speaker_batch,
        ) = await asyncio.gather(
            self.repository.get_profiles({creator_id}),
            self.repository.get_transcript(transcript_id),
            self.repository.list_transcript_speakers(transcript_id),
            self.repository.list_transcript_segments(transcript_id),
            self.repository.get_notes(notes_id),
            self.repository.list_shared_member_ids(UUID(meeting["id"])),
            self._quality_call("list_attendees", UUID(meeting["id"]), default=[]),
            self._quality_call("list_questions", UUID(meeting["id"]), default=[]),
            self._quality_call("list_segment_speaker_edits", transcript_id, default=[]),
            self._quality_call("get_latest_speaker_edit_batch", UUID(meeting["id"]), default=None),
        )
        profile = profile_map.get(str(creator_id))
        if profile is None:
            raise AppError(502, "PROFILE_NOT_FOUND", "회의록 작성자 정보를 찾을 수 없습니다.")
        speaker_names = {str(item["id"]): item["display_name"] for item in speakers}
        speaker_edit_map = {str(item["segment_id"]): item for item in speaker_edits}
        source_run_id = (
            UUID(notes["derived_from_run_id"])
            if notes and notes.get("derived_from_run_id")
            else None
        )
        actions_task = self.repository.list_action_items(UUID(meeting["id"]), source_run_id)
        if source_run_id:
            ai_run, actions = await asyncio.gather(
                self.repository.get_ai_run(source_run_id), actions_task
            )
        else:
            ai_run, actions = None, await actions_task
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
            transcript_corrected=(transcript or {}).get("corrected_text", "") or "",
            transcript_speakers=[
                TranscriptSpeakerResponse(
                    id=item["id"],
                    provider_label=item["provider_label"],
                    display_name=item["display_name"],
                )
                for item in speakers
            ],
            transcript_segments=[
                TranscriptSegmentResponse(
                    id=item["id"],
                    speaker_id=speaker_edit_map.get(str(item["id"]), {}).get(
                        "speaker_id", item["speaker_id"]
                    ),
                    speaker_name=speaker_names.get(
                        str(
                            speaker_edit_map.get(str(item["id"]), {}).get(
                                "speaker_id", item["speaker_id"]
                            )
                        ),
                        "알 수 없는 화자",
                    ),
                    start_seconds=float(item["start_seconds"]),
                    end_seconds=float(item["end_seconds"]),
                    text=item["original_text"],
                    original_speaker_id=item["speaker_id"],
                )
                for item in segments
            ],
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
            attendees=[
                {
                    "id": item["id"],
                    "user_id": item.get("user_id"),
                    "external_name": item.get("external_name"),
                    "external_organization": item.get("external_organization"),
                    "display_name": (item.get("profiles") or {}).get("display_name")
                    or item.get("external_name")
                    or "알 수 없는 참석자",
                }
                for item in attendees
            ],
            questions=questions,
            latest_speaker_edit_batch_id=(latest_speaker_batch or {}).get("id"),
        )

    def _summarize(
        self,
        meeting: dict,
        profiles: dict[str, dict],
        shared_meeting_ids: set[UUID],
    ) -> MeetingListItemResponse:
        creator_id = UUID(meeting["created_by"])
        profile = profiles.get(str(creator_id))
        if profile is None:
            raise AppError(502, "PROFILE_NOT_FOUND", "회의록 작성자 정보를 찾을 수 없습니다.")
        return MeetingListItemResponse(
            id=meeting["id"],
            team_id=meeting["team_id"],
            title=meeting["title"],
            meeting_at=meeting["meeting_at"],
            created_by=UserSummary(
                id=profile["id"],
                name=profile["display_name"],
                email=profile["email"],
                avatar_url=profile.get("avatar_url"),
            ),
            processing_status=meeting["processing_status"],
            version=meeting["version"],
            is_mine=creator_id == self.user.id,
            is_shared_with_me=UUID(meeting["id"]) in shared_meeting_ids,
        )

    async def _quality_call(self, method: str, *args: object, default: object) -> object:
        if self.quality_repository is None:
            return default
        operation = getattr(self.quality_repository, method)
        return await operation(*args)
