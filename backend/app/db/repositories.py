from typing import Any
from uuid import UUID, uuid4

from app.core.errors import AppError
from app.db.client import SupabaseRestClient

MEETING_SELECT = (
    "id,team_id,title,meeting_at,source_type,created_by,processing_status,"
    "current_transcript_id,current_notes_id,version,topic,location,meeting_type,"
    "purpose,project_name,template_id,metadata_confirmed_at"
)


class MeetFlowRepository:
    def __init__(self, client: SupabaseRestClient) -> None:
        self.client = client

    async def create_organization(
        self, name: str, description: str, user_id: UUID
    ) -> dict[str, Any]:
        organization_id = uuid4()
        await self.client.request(
            "POST",
            "organizations",
            json={
                "id": str(organization_id),
                "name": name,
                "description": description,
                "created_by": str(user_id),
            },
            prefer="return=minimal",
        )
        organization = await self.get_organization(organization_id)
        if organization is None:
            raise AppError(
                502,
                "ORGANIZATION_CREATE_INCONSISTENT",
                "조직 생성 결과를 확인할 수 없습니다.",
            )
        return organization

    async def get_organization(self, organization_id: UUID) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "organizations",
            params={
                "select": "id,name,description,created_at",
                "id": f"eq.{organization_id}",
            },
        )
        return rows[0] if rows else None

    async def list_organization_memberships(self, user_id: UUID) -> list[dict[str, Any]]:
        rows, _ = await self.client.request(
            "GET",
            "organization_members",
            params={
                "select": (
                    "organization_id,role,status,"
                    "organizations!inner(id,name,description,created_at)"
                ),
                "user_id": f"eq.{user_id}",
                "status": "eq.active",
                "order": "joined_at.asc",
            },
        )
        return rows

    async def get_organization_membership(
        self, organization_id: UUID, user_id: UUID
    ) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "organization_members",
            params={
                "select": "organization_id,user_id,role,status",
                "organization_id": f"eq.{organization_id}",
                "user_id": f"eq.{user_id}",
                "status": "eq.active",
            },
        )
        return rows[0] if rows else None

    async def create_department(
        self,
        organization_id: UUID,
        name: str,
        description: str,
        user_id: UUID,
    ) -> dict[str, Any]:
        department_id = uuid4()
        await self.client.request(
            "POST",
            "departments",
            json={
                "id": str(department_id),
                "organization_id": str(organization_id),
                "name": name,
                "description": description,
                "created_by": str(user_id),
            },
            prefer="return=minimal",
        )
        department = await self.get_department(department_id)
        if department is None:
            raise AppError(
                502,
                "DEPARTMENT_CREATE_INCONSISTENT",
                "부문 생성 결과를 확인할 수 없습니다.",
            )
        return department

    async def get_department(self, department_id: UUID) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "departments",
            params={
                "select": "id,organization_id,name,description,created_at",
                "id": f"eq.{department_id}",
            },
        )
        return rows[0] if rows else None

    async def list_departments(self, organization_id: UUID) -> list[dict[str, Any]]:
        rows, _ = await self.client.request(
            "GET",
            "departments",
            params={
                "select": "id,organization_id,name,description,created_at",
                "organization_id": f"eq.{organization_id}",
                "order": "name.asc",
            },
        )
        return rows

    async def get_department_membership(
        self, department_id: UUID, user_id: UUID
    ) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "department_members",
            params={
                "select": "department_id,user_id,role,status",
                "department_id": f"eq.{department_id}",
                "user_id": f"eq.{user_id}",
                "status": "eq.active",
            },
        )
        return rows[0] if rows else None

    async def list_department_memberships(
        self, user_id: UUID, organization_id: UUID
    ) -> list[dict[str, Any]]:
        rows, _ = await self.client.request(
            "GET",
            "department_members",
            params={
                "select": "department_id,role,departments!inner(organization_id)",
                "user_id": f"eq.{user_id}",
                "status": "eq.active",
                "departments.organization_id": f"eq.{organization_id}",
            },
        )
        return rows

    async def get_profile(self, user_id: UUID) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "profiles",
            params={"select": "id,display_name,email,avatar_url", "id": f"eq.{user_id}"},
        )
        return rows[0] if rows else None

    async def get_membership(self, team_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "team_members",
            params={
                "select": "team_id,user_id,role,status",
                "team_id": f"eq.{team_id}",
                "user_id": f"eq.{user_id}",
                "status": "eq.active",
            },
        )
        return rows[0] if rows else None

    async def create_team(
        self,
        name: str,
        user_id: UUID,
        *,
        organization_id: UUID | None = None,
        department_id: UUID | None = None,
    ) -> dict[str, Any]:
        team_id = uuid4()
        await self.client.request(
            "POST",
            "teams",
            json={
                "id": str(team_id),
                "name": name,
                "created_by": str(user_id),
                "organization_id": str(organization_id) if organization_id else None,
                "department_id": str(department_id) if department_id else None,
            },
            prefer="return=minimal",
        )
        team = await self.get_team(team_id)
        if team is None:
            raise AppError(
                502,
                "TEAM_CREATE_INCONSISTENT",
                "팀 생성 결과를 확인할 수 없습니다.",
            )
        return team

    async def list_memberships(self, user_id: UUID) -> list[dict[str, Any]]:
        rows, _ = await self.client.request(
            "GET",
            "team_members",
            params={
                "select": (
                    "team_id,role,status,teams!inner("
                    "id,name,description,created_at,organization_id,department_id,"
                    "organizations!teams_organization_id_fkey(id,name),"
                    "departments!teams_department_scope_fk(id,name))"
                ),
                "user_id": f"eq.{user_id}",
                "status": "eq.active",
                "order": "joined_at.asc",
            },
        )
        return rows

    async def get_team(self, team_id: UUID) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "teams",
            params={
                "select": (
                    "id,name,description,created_at,organization_id,department_id,"
                    "organizations!teams_organization_id_fkey(id,name),"
                    "departments!teams_department_scope_fk(id,name)"
                ),
                "id": f"eq.{team_id}",
            },
        )
        return rows[0] if rows else None

    async def list_team_members(self, team_id: UUID) -> list[dict[str, Any]]:
        rows, _ = await self.client.request(
            "GET",
            "team_members",
            params={
                "select": "user_id,role,profiles!inner(id,display_name,email,avatar_url)",
                "team_id": f"eq.{team_id}",
                "status": "eq.active",
                "order": "joined_at.asc",
            },
        )
        return rows

    async def count_team_members(self, team_ids: set[UUID]) -> dict[str, int]:
        if not team_ids:
            return {}
        ids = ",".join(str(team_id) for team_id in team_ids)
        rows, _ = await self.client.request(
            "GET",
            "team_members",
            params={
                "select": "team_id",
                "team_id": f"in.({ids})",
                "status": "eq.active",
            },
        )
        counts = {str(team_id): 0 for team_id in team_ids}
        for row in rows:
            team_id = str(row["team_id"])
            counts[team_id] = counts.get(team_id, 0) + 1
        return counts

    async def create_meeting(self, values: dict[str, Any]) -> dict[str, Any]:
        meeting_id = uuid4()
        await self.client.request(
            "POST",
            "meetings",
            json={"id": str(meeting_id), **values},
            prefer="return=minimal",
        )
        meeting = await self.get_meeting(meeting_id)
        if meeting is None:
            raise AppError(
                502,
                "MEETING_CREATE_INCONSISTENT",
                "회의록 생성 결과를 확인할 수 없습니다.",
            )
        return meeting

    async def list_meetings(self, team_id: UUID) -> list[dict[str, Any]]:
        rows, _ = await self.client.request(
            "GET",
            "meetings",
            params={
                "select": MEETING_SELECT,
                "team_id": f"eq.{team_id}",
                "deleted_at": "is.null",
                "order": "meeting_at.desc",
            },
        )
        return rows

    async def get_meeting(self, meeting_id: UUID) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "meetings",
            params={
                "select": MEETING_SELECT,
                "id": f"eq.{meeting_id}",
                "deleted_at": "is.null",
            },
        )
        return rows[0] if rows else None

    async def update_meeting(
        self, meeting_id: UUID, version: int, values: dict[str, Any]
    ) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "PATCH",
            "meetings",
            params={"id": f"eq.{meeting_id}", "version": f"eq.{version}", "deleted_at": "is.null"},
            json={**values, "version": version + 1},
            prefer="return=representation",
        )
        return rows[0] if rows else None

    async def soft_delete_meeting(self, meeting_id: UUID, version: int) -> str:
        result, _ = await self.client.request(
            "POST",
            "rpc/soft_delete_meeting",
            json={"target_meeting_id": str(meeting_id), "expected_version": version},
        )
        if not isinstance(result, str):
            raise AppError(
                502,
                "MEETING_DELETE_RESPONSE_INVALID",
                "회의록 삭제 결과를 확인할 수 없습니다.",
            )
        return result

    async def get_profiles(self, user_ids: set[UUID]) -> dict[str, dict[str, Any]]:
        if not user_ids:
            return {}
        ids = ",".join(str(user_id) for user_id in user_ids)
        rows, _ = await self.client.request(
            "GET",
            "profiles",
            params={"select": "id,display_name,email,avatar_url", "id": f"in.({ids})"},
        )
        return {row["id"]: row for row in rows}

    async def get_transcript(self, transcript_id: UUID | None) -> dict[str, Any] | None:
        if transcript_id is None:
            return None
        rows, _ = await self.client.request(
            "GET",
            "meeting_transcripts",
            params={
                "select": "id,original_text,corrected_text,edited_text",
                "id": f"eq.{transcript_id}",
            },
        )
        return rows[0] if rows else None

    async def get_latest_direct_transcript(
        self, meeting_id: UUID, user_id: UUID
    ) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "meeting_transcripts",
            params={
                "select": "id,original_text,corrected_text,edited_text",
                "meeting_id": f"eq.{meeting_id}",
                "created_by": f"eq.{user_id}",
                "source": "eq.direct",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    async def create_generated_transcript(
        self,
        *,
        meeting_id: UUID,
        user_id: UUID,
        source: str,
        text: str,
        language: str | None = None,
        stt_provider: str | None = None,
        stt_model: str | None = None,
    ) -> dict[str, Any]:
        transcript_id = uuid4()
        await self.client.request(
            "POST",
            "meeting_transcripts",
            json={
                "id": str(transcript_id),
                "meeting_id": str(meeting_id),
                "source": source,
                "original_text": text,
                "edited_text": text,
                "language": language,
                "stt_provider": stt_provider,
                "stt_model": stt_model,
                "created_by": str(user_id),
            },
            prefer="return=minimal",
        )
        transcript = await self.get_transcript(transcript_id)
        if transcript is None:
            raise AppError(
                502,
                "TRANSCRIPT_CREATE_INCONSISTENT",
                "회의 전문 저장 결과를 확인할 수 없습니다.",
            )
        return transcript

    async def create_transcript(self, meeting_id: UUID, user_id: UUID, text: str) -> dict[str, Any]:
        return await self.create_generated_transcript(
            meeting_id=meeting_id,
            user_id=user_id,
            source="direct",
            text=text,
        )

    async def create_meeting_file(self, values: dict[str, Any]) -> dict[str, Any]:
        await self.client.request("POST", "meeting_files", json=values, prefer="return=minimal")
        file = await self.get_meeting_file(UUID(values["id"]))
        if file is None:
            raise AppError(502, "FILE_CREATE_INCONSISTENT", "파일 정보를 확인할 수 없습니다.")
        return file

    async def get_meeting_file(self, file_id: UUID) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "meeting_files",
            params={
                "select": (
                    "id,meeting_id,uploaded_by,storage_bucket,storage_path,original_name,"
                    "mime_type,size_bytes,sha256,processing_status,error_code,created_at"
                    ",requested_stt_provider"
                ),
                "id": f"eq.{file_id}",
            },
        )
        return rows[0] if rows else None

    async def list_meeting_files(self, meeting_id: UUID) -> list[dict[str, Any]]:
        rows, _ = await self.client.request(
            "GET",
            "meeting_files",
            params={
                "select": (
                    "id,meeting_id,uploaded_by,storage_bucket,storage_path,original_name,"
                    "mime_type,size_bytes,sha256,processing_status,error_code,created_at"
                    ",requested_stt_provider"
                ),
                "meeting_id": f"eq.{meeting_id}",
                "order": "created_at.desc",
            },
        )
        return rows

    async def update_meeting_file(self, file_id: UUID, values: dict[str, Any]) -> dict[str, Any]:
        await self.client.request(
            "PATCH",
            "meeting_files",
            params={"id": f"eq.{file_id}"},
            json=values,
            prefer="return=minimal",
        )
        file = await self.get_meeting_file(file_id)
        if file is None:
            raise AppError(404, "FILE_NOT_FOUND", "파일 정보를 찾을 수 없습니다.")
        return file

    async def update_transcript(self, transcript_id: UUID, text: str) -> dict[str, Any]:
        rows, _ = await self.client.request(
            "PATCH",
            "meeting_transcripts",
            params={"id": f"eq.{transcript_id}"},
            json={"edited_text": text},
            prefer="return=representation",
        )
        return rows[0]

    async def create_transcript_diarization(
        self,
        *,
        meeting_id: UUID,
        transcript_id: UUID,
        speakers: list[dict[str, str]],
        segments: list[dict[str, object]],
    ) -> None:
        if not speakers or not segments:
            return
        speaker_ids = {item["speaker_key"]: uuid4() for item in speakers}
        await self.client.request(
            "POST",
            "transcript_speakers",
            json=[
                {
                    "id": str(speaker_ids[item["speaker_key"]]),
                    "transcript_id": str(transcript_id),
                    "meeting_id": str(meeting_id),
                    "speaker_key": item["speaker_key"],
                    "provider_label": item["provider_label"],
                    "display_name": item["display_name"],
                }
                for item in speakers
            ],
            prefer="return=minimal",
        )
        await self.client.request(
            "POST",
            "transcript_segments",
            json=[
                {
                    "id": str(uuid4()),
                    "transcript_id": str(transcript_id),
                    "meeting_id": str(meeting_id),
                    "speaker_id": str(speaker_ids[str(item["speaker_key"])]),
                    "segment_index": index,
                    "start_seconds": item["start"],
                    "end_seconds": item["end"],
                    "original_text": item["text"],
                }
                for index, item in enumerate(segments)
            ],
            prefer="return=minimal",
        )

    async def list_transcript_speakers(self, transcript_id: UUID | None) -> list[dict[str, Any]]:
        if transcript_id is None:
            return []
        rows, _ = await self.client.request(
            "GET",
            "transcript_speakers",
            params={
                "select": "id,speaker_key,provider_label,display_name",
                "transcript_id": f"eq.{transcript_id}",
                "order": "created_at.asc",
            },
        )
        return rows

    async def list_transcript_segments(self, transcript_id: UUID | None) -> list[dict[str, Any]]:
        if transcript_id is None:
            return []
        rows, _ = await self.client.request(
            "GET",
            "transcript_segments",
            params={
                "select": ("id,speaker_id,segment_index,start_seconds,end_seconds,original_text"),
                "transcript_id": f"eq.{transcript_id}",
                "order": "segment_index.asc",
            },
        )
        return rows

    async def update_transcript_speaker(self, speaker_id: UUID, display_name: str) -> None:
        await self.client.request(
            "PATCH",
            "transcript_speakers",
            params={"id": f"eq.{speaker_id}"},
            json={"display_name": display_name},
            prefer="return=minimal",
        )

    async def get_notes(self, notes_id: UUID | None) -> dict[str, Any] | None:
        if notes_id is None:
            return None
        rows, _ = await self.client.request(
            "GET",
            "meeting_notes",
            params={
                "select": "summary,key_discussions,decisions,follow_ups,derived_from_run_id",
                "id": f"eq.{notes_id}",
            },
        )
        return rows[0] if rows else None

    async def update_notes(self, notes_id: UUID, values: dict[str, Any]) -> dict[str, Any]:
        await self.client.request(
            "PATCH",
            "meeting_notes",
            params={"id": f"eq.{notes_id}"},
            json=values,
            prefer="return=minimal",
        )
        notes = await self.get_notes(notes_id)
        if notes is None:
            raise AppError(404, "NOTES_NOT_FOUND", "회의 분석 결과를 찾을 수 없습니다.")
        return notes

    async def list_action_items(
        self, meeting_id: UUID, source_run_id: UUID | None = None
    ) -> list[dict[str, Any]]:
        params = {
            "select": "id,description,assignee_id,assignee_text,due_date,status",
            "meeting_id": f"eq.{meeting_id}",
            "order": "sort_order.asc",
        }
        if source_run_id:
            params["or"] = f"(source_run_id.eq.{source_run_id},source_run_id.is.null)"
        else:
            params["source_run_id"] = "is.null"
        rows, _ = await self.client.request(
            "GET",
            "action_items",
            params=params,
        )
        return rows

    async def get_ai_run(self, run_id: UUID | None) -> dict[str, Any] | None:
        if run_id is None:
            return None
        rows, _ = await self.client.request(
            "GET",
            "meeting_ai_runs",
            params={"select": "id,completed_at", "id": f"eq.{run_id}"},
        )
        return rows[0] if rows else None

    async def list_shared_member_ids(self, meeting_id: UUID) -> list[UUID]:
        rows, _ = await self.client.request(
            "GET", "meeting_shares", params={"select": "user_id", "meeting_id": f"eq.{meeting_id}"}
        )
        return [UUID(row["user_id"]) for row in rows]

    async def replace_meeting_shares(
        self, meeting_id: UUID, shared_by: UUID, shares: list[dict[str, Any]]
    ) -> None:
        del shared_by
        await self.client.request(
            "POST",
            "rpc/replace_meeting_shares",
            json={"target_meeting_id": str(meeting_id), "target_shares": shares},
        )

    async def list_shared_meeting_ids(self, user_id: UUID, meeting_ids: set[UUID]) -> set[UUID]:
        if not meeting_ids:
            return set()
        ids = ",".join(str(meeting_id) for meeting_id in meeting_ids)
        rows, _ = await self.client.request(
            "GET",
            "meeting_shares",
            params={
                "select": "meeting_id",
                "meeting_id": f"in.({ids})",
                "user_id": f"eq.{user_id}",
            },
        )
        return {UUID(row["meeting_id"]) for row in rows}

    async def create_invitation(self, values: dict[str, Any]) -> dict[str, Any]:
        await self.client.request("POST", "team_invitations", json=values, prefer="return=minimal")
        rows, _ = await self.client.request(
            "GET",
            "team_invitations",
            params={
                "select": "id,team_id,email_normalized,role,expires_at",
                "id": f"eq.{values['id']}",
            },
        )
        return rows[0]

    async def accept_invitation(self, token_hash: str) -> UUID:
        value, _ = await self.client.request(
            "POST", "rpc/accept_team_invitation", json={"target_token_hash": token_hash}
        )
        return UUID(str(value))

    async def cancel_invitation(self, team_id: UUID, invitation_id: UUID) -> bool:
        value, _ = await self.client.request(
            "POST",
            "rpc/cancel_team_invitation",
            json={"target_team_id": str(team_id), "target_invitation_id": str(invitation_id)},
        )
        return bool(value)

    async def decline_invitation(self, token_hash: str) -> bool:
        value, _ = await self.client.request(
            "POST", "rpc/decline_team_invitation", json={"target_token_hash": token_hash}
        )
        return bool(value)
