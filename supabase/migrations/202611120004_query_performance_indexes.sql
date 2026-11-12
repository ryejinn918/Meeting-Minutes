-- Align indexes with the actual list queries used by the mobile UI.
create index if not exists meetings_team_meeting_at_idx
  on public.meetings(team_id, meeting_at desc)
  where deleted_at is null;

create index if not exists team_members_team_joined_active_idx
  on public.team_members(team_id, joined_at asc)
  where status = 'active';
