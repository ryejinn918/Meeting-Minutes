from pathlib import Path


def test_diarization_migration_has_rls_and_private_checkpoint_segments() -> None:
    migration = Path(
        "../supabase/migrations/202611120003_diarized_transcripts.sql"
    ).read_text(encoding="utf-8")

    assert "add column segments jsonb" in migration
    assert "create table public.transcript_speakers" in migration
    assert "create table public.transcript_segments" in migration
    assert "enable row level security" in migration
    assert "private.can_view_meeting(meeting_id)" in migration
    assert "private.can_manage_meeting(meeting_id)" in migration
    assert "grant update(display_name)" in migration
    assert "disable row level security" not in migration.lower()
    assert "grant all" not in migration.lower()
