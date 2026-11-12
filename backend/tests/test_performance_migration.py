from pathlib import Path


def test_performance_indexes_match_list_filters_and_order() -> None:
    migration = (
        Path(__file__).parents[2]
        / "supabase"
        / "migrations"
        / "202611120004_query_performance_indexes.sql"
    ).read_text(encoding="utf-8")

    assert "meetings(team_id, meeting_at desc)" in migration
    assert "where deleted_at is null" in migration
    assert "team_members(team_id, joined_at asc)" in migration
    assert "where status = 'active'" in migration
