from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.db.client import SupabaseRestClient


class QualityRepository:
    def __init__(self, client: SupabaseRestClient) -> None:
        self.client = client

    async def list_templates(self, team: dict[str, Any]) -> list[dict[str, Any]]:
        filters = [f"team_id.eq.{team['id']}"]
        if team.get("organization_id"):
            filters.append(f"organization_id.eq.{team['organization_id']}")
        rows, _ = await self.client.request(
            "GET",
            "meeting_templates",
            params={
                "select": (
                    "id,organization_id,department_id,team_id,name,description,"
                    "meeting_type,sections,writing_rules,is_default,version,is_active,created_at"
                ),
                "or": f"({','.join(filters)})",
                "is_active": "eq.true",
                "order": "is_default.desc,updated_at.desc",
            },
        )
        department_id = team.get("department_id")
        return [
            row
            for row in rows
            if row.get("team_id") == team["id"]
            or row.get("department_id") is None
            or row.get("department_id") == department_id
        ]

    async def get_template(self, template_id: UUID) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "meeting_templates",
            params={"select": "*", "id": f"eq.{template_id}"},
        )
        return rows[0] if rows else None

    async def create_template(self, values: dict[str, Any]) -> dict[str, Any]:
        template_id = uuid4()
        await self.client.request(
            "POST",
            "meeting_templates",
            json={"id": str(template_id), **values},
            prefer="return=minimal",
        )
        template = await self.get_template(template_id)
        if template is None:
            raise RuntimeError("created template is not visible")
        return template

    async def update_template(
        self, template_id: UUID, values: dict[str, Any]
    ) -> dict[str, Any] | None:
        current = await self.get_template(template_id)
        if current is None:
            return None
        await self.client.request(
            "PATCH",
            "meeting_templates",
            params={"id": f"eq.{template_id}"},
            json={**values, "version": int(current["version"]) + 1},
            prefer="return=minimal",
        )
        return await self.get_template(template_id)

    async def delete_template(self, template_id: UUID) -> None:
        await self.client.request(
            "PATCH",
            "meeting_templates",
            params={"id": f"eq.{template_id}"},
            json={"is_active": False},
            prefer="return=minimal",
        )

    async def list_glossary(self, team: dict[str, Any]) -> list[dict[str, Any]]:
        filters = [f"team_id.eq.{team['id']}"]
        if team.get("organization_id"):
            filters.append(f"organization_id.eq.{team['organization_id']}")
        rows, _ = await self.client.request(
            "GET",
            "glossary_terms",
            params={
                "select": (
                    "id,organization_id,department_id,team_id,term,preferred_term,"
                    "aliases,description,created_at"
                ),
                "or": f"({','.join(filters)})",
                "order": "term.asc",
            },
        )
        department_id = team.get("department_id")
        return [
            row
            for row in rows
            if row.get("team_id") == team["id"]
            or row.get("department_id") is None
            or row.get("department_id") == department_id
        ]

    async def get_glossary_term(self, term_id: UUID) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET", "glossary_terms", params={"select": "*", "id": f"eq.{term_id}"}
        )
        return rows[0] if rows else None

    async def create_glossary_term(self, values: dict[str, Any]) -> dict[str, Any]:
        term_id = uuid4()
        await self.client.request(
            "POST",
            "glossary_terms",
            json={"id": str(term_id), **values},
            prefer="return=minimal",
        )
        term = await self.get_glossary_term(term_id)
        if term is None:
            raise RuntimeError("created glossary term is not visible")
        return term

    async def update_glossary_term(
        self, term_id: UUID, values: dict[str, Any]
    ) -> dict[str, Any] | None:
        await self.client.request(
            "PATCH",
            "glossary_terms",
            params={"id": f"eq.{term_id}"},
            json=values,
            prefer="return=minimal",
        )
        return await self.get_glossary_term(term_id)

    async def delete_glossary_term(self, term_id: UUID) -> None:
        await self.client.request("DELETE", "glossary_terms", params={"id": f"eq.{term_id}"})

    async def set_attendees(self, meeting_id: UUID, attendees: list[dict[str, Any]]) -> None:
        await self.client.request(
            "POST",
            "rpc/set_meeting_attendees",
            json={"target_meeting_id": str(meeting_id), "attendee_items": attendees},
        )

    async def list_attendees(self, meeting_id: UUID) -> list[dict[str, Any]]:
        rows, _ = await self.client.request(
            "GET",
            "meeting_attendees",
            params={
                "select": (
                    "id,user_id,external_name,external_organization,profiles(id,display_name)"
                ),
                "meeting_id": f"eq.{meeting_id}",
                "order": "created_at.asc",
            },
        )
        return rows

    async def save_correction(
        self,
        *,
        meeting_id: UUID,
        transcript_id: UUID,
        corrected_text: str,
        changes: list[dict[str, Any]],
        uncertainties: list[dict[str, Any]],
        context: dict[str, Any],
        provider: str,
        model: str,
    ) -> UUID:
        result, _ = await self.client.request(
            "POST",
            "rpc/save_transcript_correction",
            json={
                "target_meeting_id": str(meeting_id),
                "target_transcript_id": str(transcript_id),
                "corrected_value": corrected_text,
                "correction_changes": changes,
                "correction_uncertainties": uncertainties,
                "context_value": context,
                "provider_value": provider,
                "model_value": model,
            },
        )
        return UUID(str(result))

    async def list_questions(self, meeting_id: UUID) -> list[dict[str, Any]]:
        rows, _ = await self.client.request(
            "GET",
            "meeting_questions",
            params={"select": "*", "meeting_id": f"eq.{meeting_id}", "order": "created_at.asc"},
        )
        return rows

    async def create_question(self, values: dict[str, Any]) -> dict[str, Any]:
        question_id = uuid4()
        await self.client.request(
            "POST",
            "meeting_questions",
            json={"id": str(question_id), **values},
            prefer="return=minimal",
        )
        rows, _ = await self.client.request(
            "GET", "meeting_questions", params={"select": "*", "id": f"eq.{question_id}"}
        )
        return rows[0]

    async def answer_question(
        self,
        meeting_id: UUID,
        question_id: UUID,
        user_id: UUID,
        answer: str | None,
        status: str,
    ) -> dict[str, Any] | None:
        await self.client.request(
            "PATCH",
            "meeting_questions",
            params={"id": f"eq.{question_id}", "meeting_id": f"eq.{meeting_id}"},
            json={
                "answer": answer,
                "status": status,
                "answered_by": str(user_id),
                "answered_at": datetime.now(UTC).isoformat(),
            },
            prefer="return=minimal",
        )
        rows, _ = await self.client.request(
            "GET",
            "meeting_questions",
            params={
                "select": "*",
                "id": f"eq.{question_id}",
                "meeting_id": f"eq.{meeting_id}",
            },
        )
        return rows[0] if rows else None

    async def apply_speaker_edit(
        self,
        meeting_id: UUID,
        segment_id: UUID,
        speaker_id: UUID,
        scope: str,
    ) -> UUID:
        result, _ = await self.client.request(
            "POST",
            "rpc/apply_transcript_speaker_edit",
            json={
                "target_meeting_id": str(meeting_id),
                "target_segment_id": str(segment_id),
                "target_speaker_id": str(speaker_id),
                "edit_scope": scope,
            },
        )
        return UUID(str(result))

    async def undo_speaker_edit(self, batch_id: UUID) -> int:
        result, _ = await self.client.request(
            "POST",
            "rpc/undo_transcript_speaker_edit",
            json={"target_batch_id": str(batch_id)},
        )
        return int(result)

    async def get_speaker_edit_batch(self, batch_id: UUID) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "transcript_speaker_edit_batches",
            params={
                "select": "id,meeting_id,changes,reverted_at",
                "id": f"eq.{batch_id}",
            },
        )
        return rows[0] if rows else None

    async def list_segment_speaker_edits(self, transcript_id: UUID | None) -> list[dict[str, Any]]:
        if transcript_id is None:
            return []
        rows, _ = await self.client.request(
            "GET",
            "transcript_segment_speaker_edits",
            params={
                "select": "segment_id,speaker_id,batch_id,updated_at",
                "transcript_id": f"eq.{transcript_id}",
            },
        )
        return rows

    async def get_latest_speaker_edit_batch(self, meeting_id: UUID) -> dict[str, Any] | None:
        rows, _ = await self.client.request(
            "GET",
            "transcript_speaker_edit_batches",
            params={
                "select": "id,changes,created_at",
                "meeting_id": f"eq.{meeting_id}",
                "reverted_at": "is.null",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    async def create_review(
        self, meeting_id: UUID, status: str, note: str, version: int, user_id: UUID
    ) -> dict[str, Any]:
        review_id = uuid4()
        await self.client.request(
            "POST", "meeting_reviews",
            json={"id": str(review_id), "meeting_id": str(meeting_id), "status": status,
                  "note": note, "version": version, "created_by": str(user_id)},
            prefer="return=minimal",
        )
        await self.client.request(
            "PATCH", "meetings", params={"id": f"eq.{meeting_id}"},
            json={
                "review_status": status,
                "approved_at": datetime.now(UTC).isoformat() if status == "approved" else None,
                "approved_by": str(user_id) if status == "approved" else None,
                "approval_version": version if status == "approved" else None,
            }, prefer="return=minimal",
        )
        rows, _ = await self.client.request(
            "GET",
            "meeting_reviews",
            params={
                "select": "status,note,version,created_at",
                "id": f"eq.{review_id}",
            },
        )
        if not rows:
            raise RuntimeError("created review is not visible")
        return rows[0]

    async def upsert_voice_profile(
        self, team_id: UUID, user_id: UUID, label: str, consented: bool
    ) -> dict[str, Any]:
        profile_id = uuid4()
        await self.client.request(
            "POST", "team_voice_profiles",
            json={"id": str(profile_id), "team_id": str(team_id), "user_id": str(user_id),
                  "label": label,
                  "consented_at": datetime.now(UTC).isoformat() if consented else None,
                  "revoked_at": None if consented else datetime.now(UTC).isoformat()},
            params={"on_conflict": "team_id,user_id"},
            prefer="resolution=merge-duplicates,return=minimal",
        )
        rows, _ = await self.client.request(
            "GET",
            "team_voice_profiles",
            params={
                "select": "id,team_id,user_id,label,consented_at,revoked_at",
                "team_id": f"eq.{team_id}",
                "user_id": f"eq.{user_id}",
            },
        )
        if not rows:
            raise RuntimeError("voice profile is not visible")
        return rows[0]
