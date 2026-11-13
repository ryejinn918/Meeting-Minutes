from pathlib import Path


def test_review_workflow_migration_is_additive_and_scoped() -> None:
    migration = Path(
        "../supabase/migrations/202611130003_speaker_review_workflow.sql"
    ).read_text(encoding="utf-8").lower()
    assert "alter table public.meetings" in migration
    assert "review_status" in migration
    assert "meeting_reviews" in migration
    assert "team_voice_profiles" in migration
    assert "enable row level security" in migration
    assert "private.can_view_meeting" in migration
    assert "private.can_manage_meeting" in migration
    assert "drop table" not in migration
