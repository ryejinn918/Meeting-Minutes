from pathlib import Path


def test_large_audio_migration_keeps_chunks_private_and_minimal() -> None:
    migration = Path("../supabase/migrations/202611120002_large_audio_chunking.sql").read_text(
        encoding="utf-8"
    )

    assert "add column usage jsonb" in migration
    assert "create table public.processing_job_chunks" in migration
    assert "alter table public.processing_job_chunks enable row level security" in migration
    assert "revoke all on public.processing_job_chunks from anon, authenticated" in migration
    assert "grant select, insert, update, delete" in migration
    assert "grant all" not in migration.lower()
    assert "disable row level security" not in migration.lower()
