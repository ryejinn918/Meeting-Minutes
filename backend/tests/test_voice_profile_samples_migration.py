from pathlib import Path


def test_voice_profile_sample_migration_is_additive_and_private_metadata_only() -> None:
    migration = Path(
        "../supabase/migrations/202611170004_voice_profile_samples.sql"
    ).read_text(encoding="utf-8").lower()

    assert "add column if not exists sample_object_path" in migration
    assert "sample_sha256" in migration
    assert "sample_size_bytes between 1 and 104857600" in migration
    assert "grant select, update" in migration
    assert "drop table" not in migration
    assert "delete from" not in migration
    assert "enable row level security" not in migration
