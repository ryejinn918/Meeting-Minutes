from pathlib import Path


def test_file_migration_keeps_private_storage_and_minimal_grants() -> None:
    migration = Path("../supabase/migrations/202611120001_file_ingestion.sql").read_text(
        encoding="utf-8"
    )

    assert "create table public.meeting_files" in migration
    assert "public = false" in migration
    assert "alter table public.meeting_files enable row level security" in migration
    assert "private.can_view_meeting(mf.meeting_id)" in migration
    assert "private.can_manage_meeting(mf.meeting_id)" in migration
    assert "grant all" not in migration.lower()
    assert "disable row level security" not in migration.lower()
