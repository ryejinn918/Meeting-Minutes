from typing import Any
from uuid import UUID, uuid4

from app.core.errors import AppError
from app.db.client import SupabaseRestClient

MEETING_SELECT = (
    "id,team_id,title,meeting_at,created_by,processing_status,"
    "current_transcript_id,current_notes_id,version"
)


class MeetFlowRepository:
    def __init__(self, client: SupabaseRestClient) -> None:
        self.client = client

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

    async def create_team(self, name: str, user_id: UUID) -> dict[str, Any]:
        team_id = uuid4()
        await self.client.request(
            "POST",
            "teams",
            json={"id": str(team_id), "name": name, "created_by": str(user_id)},
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
                "select": "team_id,role,status,teams!inner(id,name,description,created_at)",
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
            params={"select": "id,name,description,created_at", "id": f"eq.{team_id}"},
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

    async def soft_delete_meeting(self, meeting_id: UUID, version: int, deleted_at: str) -> None:
        await self.client.request(
            "PATCH",
            "meetings",
            params={"id": f"eq.{meeting_id}", "version": f"eq.{version}", "deleted_at": "is.null"},
            json={"deleted_at": deleted_at, "version": version + 1},
            prefer="return=minimal",
        )

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
            params={"select": "id,original_text,edited_text", "id": f"eq.{transcript_id}"},
        )
        return rows[0] if rows else None

    async def get_latest_direct_transcript(
        self, meeting_id: UUID, user_id: UUID
    ) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "meeting_transcripts",
            params={
                "select": "id,original_text,edited_text",
                "meeting_id": f"eq.{meeting_id}",
                "created_by": f"eq.{user_id}",
                "source": "eq.direct",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    async def create_transcript(self, meeting_id: UUID, user_id: UUID, text: str) -> dict[str, Any]:
        transcript_id = uuid4()
        await self.client.request(
            "POST",
            "meeting_transcripts",
            json={
                "id": str(transcript_id),
                "meeting_id": str(meeting_id),
                "source": "direct",
                "original_text": text,
                "edited_text": text,
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

    async def update_transcript(self, transcript_id: UUID, text: str) -> dict[str, Any]:
        rows, _ = await self.client.request(
            "PATCH",
            "meeting_transcripts",
            params={"id": f"eq.{transcript_id}"},
            json={"edited_text": text},
            prefer="return=representation",
        )
        return rows[0]

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
