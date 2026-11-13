from datetime import date
from pathlib import Path

import pytest

from app.ai.analysis.mock_provider import MockAnalysisProvider
from app.schemas.meetings import MeetingCreate
from app.schemas.quality import GlossaryTermCreate, QuestionAnswer


def migration_text() -> str:
    return (
        Path(__file__).parents[2]
        / "supabase"
        / "migrations"
        / "202611130001_phase_b_meeting_quality.sql"
    ).read_text(encoding="utf-8")


def test_phase_b_migration_keeps_legacy_rows_and_protects_scopes() -> None:
    sql = migration_text().lower()
    assert "update public.teams" not in sql
    assert "update public.meetings set organization_id" not in sql
    assert "drop table" not in sql
    assert "quality_scope_is_consistent" in sql
    assert "meeting_templates_validate_scope" in sql
    assert "glossary_terms_validate_scope" in sql
    assert "alter table public.meeting_templates enable row level security" in sql
    assert "alter table public.glossary_terms enable row level security" in sql
    assert "meeting_templates_insert_manager" in sql
    assert "meeting_templates_update_manager" in sql
    assert "meeting_templates_delete_manager" in sql
    assert "private.is_active_department_member" in sql
    assert "t.department_id = target_department_id" in sql
    assert "can_view_quality_scope(organization_id, department_id, team_id)" in sql


def test_phase_b_migration_uses_atomic_correction_and_speaker_edit_rpcs() -> None:
    sql = migration_text().lower()
    assert "public.save_transcript_correction" in sql
    assert "public.apply_transcript_speaker_edit" in sql
    assert "public.undo_transcript_speaker_edit" in sql
    assert "original_text text not null" in sql
    assert "add column corrected_text text" in sql
    assert "meeting_template_versions" in sql


def test_legacy_meeting_create_defaults_remain_compatible() -> None:
    payload = MeetingCreate.model_validate(
        {
            "team_id": "22222222-2222-4222-8222-222222222222",
            "title": "기존 회의",
            "meeting_at": "2026-11-13T09:00:00+09:00",
        }
    )
    assert payload.meeting_type == "general"
    assert payload.topic == ""
    assert payload.attendees == []


def test_glossary_is_optional_but_department_requires_organization() -> None:
    with pytest.raises(ValueError):
        GlossaryTermCreate.model_validate(
            {
                "department_id": "33333333-3333-4333-8333-333333333333",
                "term": "가상 용어",
                "preferred_term": "가상 표준 용어",
            }
        )


def test_answered_question_requires_answer() -> None:
    with pytest.raises(ValueError):
        QuestionAnswer(answer="", status="answered")


@pytest.mark.asyncio
async def test_mock_correction_uses_only_supplied_fake_glossary() -> None:
    result = await MockAnalysisProvider().correct_transcript(
        "가상별칭을 검토했다.",
        topic="가상 프로젝트",
        glossary=[
            {
                "term": "가상용어",
                "preferred_term": "가상 표준 용어",
                "aliases": ["가상별칭"],
            }
        ],
    )
    assert result.correction.corrected_text == "가상 표준 용어을 검토했다."
    assert result.usage["mock"] is True


@pytest.mark.asyncio
async def test_mock_analysis_accepts_phase_b_context() -> None:
    result = await MockAnalysisProvider().analyze(
        "가상 회의 전문",
        meeting_date=date(2026, 11, 13),
        context={"meeting_type": "project", "topic": "가상 주제"},
    )
    assert result.usage["context_supplied"] is True
