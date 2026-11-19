from pathlib import Path


def test_soft_delete_permissions_migration_is_minimal_and_keeps_rls() -> None:
    sql = (
        Path(__file__).parents[2]
        / "supabase"
        / "migrations"
        / "202611170003_soft_delete_rpc_permissions.sql"
    ).read_text(encoding="utf-8")

    assert "grant execute on function public.soft_delete_meeting(uuid, integer)" in sql
    assert "grant execute on function private.can_manage_meeting(uuid, uuid)" in sql
    assert "grant update(version, deleted_at) on public.meetings" in sql
    assert "grant select on public.processing_jobs" in sql
    assert "disable row level security" not in sql.lower()
    assert "delete from" not in sql.lower()
    assert "truncate" not in sql.lower()
