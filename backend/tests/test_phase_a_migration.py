from pathlib import Path


def test_phase_a_migration_preserves_legacy_teams_and_adds_scope() -> None:
    sql = (
        Path(__file__).parents[2]
        / "supabase"
        / "migrations"
        / "202611120005_organization_hierarchy_and_safe_delete.sql"
    ).read_text(encoding="utf-8")

    assert "create table public.organizations" in sql
    assert "create table public.departments" in sql
    assert "add column organization_id uuid" in sql
    assert "add column department_id uuid" in sql
    assert "update public.teams" not in sql
    assert "create policy teams_insert_scoped" in sql
    assert "create or replace function public.soft_delete_meeting" in sql
    assert "pj.status in ('queued', 'processing')" in sql
    assert "security invoker" in sql
    assert "grant execute on function public.soft_delete_meeting" in sql


def test_phase_a_migration_enables_rls_for_new_tables() -> None:
    sql = (
        Path(__file__).parents[2]
        / "supabase"
        / "migrations"
        / "202611120005_organization_hierarchy_and_safe_delete.sql"
    ).read_text(encoding="utf-8")

    for table in (
        "organizations",
        "organization_members",
        "departments",
        "department_members",
    ):
        assert f"alter table public.{table} enable row level security" in sql
        assert f"revoke all on public.{table} from anon, authenticated" in sql
