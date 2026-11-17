-- Optional team-level context used for conservative transcript correction.
alter table public.teams
  add column if not exists project_topic text not null default '';

alter table public.teams
  add constraint teams_project_topic_length
  check (char_length(project_topic) <= 500);

grant update(project_topic) on public.teams to authenticated;
