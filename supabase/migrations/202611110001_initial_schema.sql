begin;

create schema if not exists private;
revoke all on schema private from public;

create type public.team_role as enum ('owner', 'admin', 'member');
create type public.member_status as enum ('active', 'removed');
create type public.meeting_source_type as enum ('direct', 'txt', 'pdf', 'audio');
create type public.meeting_processing_status as enum (
  'draft', 'uploaded', 'transcribing', 'analyzing', 'ready', 'failed'
);
create type public.action_status as enum ('todo', 'in_progress', 'done');
create type public.job_type as enum ('extract', 'transcribe', 'analyze');
create type public.job_status as enum ('queued', 'processing', 'succeeded', 'failed');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null check (char_length(display_name) between 1 and 100),
  email text not null,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.teams (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 2 and 50),
  description text not null default '',
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.team_members (
  team_id uuid not null references public.teams(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role public.team_role not null default 'member',
  status public.member_status not null default 'active',
  joined_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (team_id, user_id)
);

create table public.meetings (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references public.teams(id) on delete cascade,
  title text not null check (char_length(title) between 1 and 100),
  meeting_at timestamptz not null,
  source_type public.meeting_source_type not null,
  created_by uuid not null references public.profiles(id) on delete restrict,
  processing_status public.meeting_processing_status not null default 'draft',
  current_transcript_id uuid,
  current_notes_id uuid,
  version integer not null default 1 check (version > 0),
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.meeting_transcripts (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  source public.meeting_source_type not null,
  original_text text not null,
  edited_text text not null,
  language text,
  stt_provider text,
  stt_model text,
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.meeting_ai_runs (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  transcript_id uuid not null references public.meeting_transcripts(id) on delete restrict,
  provider text not null,
  model text not null,
  prompt_version text not null,
  schema_version text not null,
  validated_output jsonb,
  usage jsonb,
  error_code text,
  completed_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.meeting_notes (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  derived_from_run_id uuid references public.meeting_ai_runs(id) on delete set null,
  summary text not null default '',
  key_discussions jsonb not null default '[]'::jsonb,
  decisions jsonb not null default '[]'::jsonb,
  follow_ups jsonb not null default '[]'::jsonb,
  updated_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.action_items (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  source_run_id uuid references public.meeting_ai_runs(id) on delete set null,
  description text not null check (char_length(description) > 0),
  assignee_id uuid references public.profiles(id) on delete set null,
  assignee_text text,
  due_date date,
  status public.action_status not null default 'todo',
  evidence text,
  sort_order integer not null default 0,
  updated_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.meeting_shares (
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  shared_by uuid not null references public.profiles(id) on delete restrict,
  can_edit boolean not null default false check (can_edit = false),
  created_at timestamptz not null default now(),
  primary key (meeting_id, user_id)
);

create table public.processing_jobs (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  job_type public.job_type not null,
  status public.job_status not null default 'queued',
  attempt_count integer not null default 0 check (attempt_count >= 0),
  error_code text,
  error_message_safe text,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.meetings
  add constraint meetings_current_transcript_fk
  foreign key (current_transcript_id) references public.meeting_transcripts(id) on delete set null,
  add constraint meetings_current_notes_fk
  foreign key (current_notes_id) references public.meeting_notes(id) on delete set null;

create index team_members_user_status_idx on public.team_members(user_id, status);
create index meetings_team_created_idx on public.meetings(team_id, created_at desc) where deleted_at is null;
create index meeting_transcripts_meeting_idx on public.meeting_transcripts(meeting_id, created_at desc);
create index action_items_meeting_status_idx on public.action_items(meeting_id, status, sort_order);
create index meeting_shares_user_meeting_idx on public.meeting_shares(user_id, meeting_id);
create index processing_jobs_meeting_created_idx on public.processing_jobs(meeting_id, created_at desc);
create unique index processing_jobs_one_active_idx
  on public.processing_jobs(meeting_id, job_type)
  where status in ('queued', 'processing');

create or replace function private.is_active_team_member(target_team_id uuid, target_user_id uuid default auth.uid())
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.team_members tm
    where tm.team_id = target_team_id
      and tm.user_id = target_user_id
      and tm.status = 'active'
  );
$$;

create or replace function private.is_team_manager(target_team_id uuid, target_user_id uuid default auth.uid())
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.team_members tm
    where tm.team_id = target_team_id
      and tm.user_id = target_user_id
      and tm.status = 'active'
      and tm.role in ('owner', 'admin')
  );
$$;

create or replace function private.can_view_meeting(target_meeting_id uuid, target_user_id uuid default auth.uid())
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.meetings m
    where m.id = target_meeting_id
      and m.deleted_at is null
      and private.is_active_team_member(m.team_id, target_user_id)
      and (
        m.created_by = target_user_id
        or private.is_team_manager(m.team_id, target_user_id)
        or exists (
          select 1 from public.meeting_shares ms
          where ms.meeting_id = m.id and ms.user_id = target_user_id
        )
      )
  );
$$;

create or replace function private.can_manage_meeting(target_meeting_id uuid, target_user_id uuid default auth.uid())
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.meetings m
    where m.id = target_meeting_id
      and private.is_active_team_member(m.team_id, target_user_id)
      and (m.created_by = target_user_id or private.is_team_manager(m.team_id, target_user_id))
  );
$$;

create or replace function private.shares_active_team_with(target_user_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.team_members mine
    join public.team_members theirs on theirs.team_id = mine.team_id
    where mine.user_id = auth.uid() and mine.status = 'active'
      and theirs.user_id = target_user_id and theirs.status = 'active'
  );
$$;

grant usage on schema private to authenticated;
revoke all on all functions in schema private from public;
grant execute on function private.is_active_team_member(uuid, uuid) to authenticated;
grant execute on function private.is_team_manager(uuid, uuid) to authenticated;
grant execute on function private.can_view_meeting(uuid, uuid) to authenticated;
grant execute on function private.can_manage_meeting(uuid, uuid) to authenticated;
grant execute on function private.shares_active_team_with(uuid) to authenticated;

create or replace function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles(id, display_name, email)
  values (
    new.id,
    coalesce(nullif(trim(new.raw_user_meta_data ->> 'display_name'), ''), split_part(new.email, '@', 1)),
    coalesce(new.email, '')
  );
  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function private.handle_new_user();

-- Backfill profiles when this migration is applied to a development project
-- that already has Auth users. The trigger above covers subsequent sign-ups.
insert into public.profiles(id, display_name, email)
select
  u.id,
  coalesce(
    nullif(trim(u.raw_user_meta_data ->> 'display_name'), ''),
    split_part(u.email, '@', 1)
  ),
  coalesce(u.email, '')
from auth.users u
on conflict (id) do nothing;

create or replace function private.handle_user_email_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.profiles set email = coalesce(new.email, '') where id = new.id;
  return new;
end;
$$;

create trigger on_auth_user_email_changed
after update of email on auth.users
for each row when (old.email is distinct from new.email)
execute function private.handle_user_email_change();

create or replace function private.handle_new_team()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.team_members(team_id, user_id, role, status)
  values (new.id, new.created_by, 'owner', 'active');
  return new;
end;
$$;

create trigger on_team_created
after insert on public.teams
for each row execute function private.handle_new_team();

create or replace function private.validate_meeting_current_refs()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.current_transcript_id is not null and not exists (
    select 1 from public.meeting_transcripts mt
    where mt.id = new.current_transcript_id and mt.meeting_id = new.id
  ) then
    raise exception 'current transcript must belong to the same meeting';
  end if;
  if new.current_notes_id is not null and not exists (
    select 1 from public.meeting_notes mn
    where mn.id = new.current_notes_id and mn.meeting_id = new.id
  ) then
    raise exception 'current notes must belong to the same meeting';
  end if;
  return new;
end;
$$;

create trigger validate_meeting_current_refs_before_write
before insert or update of current_transcript_id, current_notes_id on public.meetings
for each row execute function private.validate_meeting_current_refs();

create or replace function private.protect_meeting_identity()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.team_id is distinct from old.team_id
    or new.created_by is distinct from old.created_by
    or new.source_type is distinct from old.source_type then
    raise exception 'meeting identity fields are immutable';
  end if;
  if new.version <> old.version + 1 then
    raise exception 'meeting version must increment by exactly one';
  end if;
  return new;
end;
$$;

create trigger protect_meeting_identity_before_update
before update on public.meetings
for each row execute function private.protect_meeting_identity();

create or replace function private.protect_transcript_original()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.meeting_id is distinct from old.meeting_id
    or new.created_by is distinct from old.created_by
    or new.source is distinct from old.source
    or new.original_text is distinct from old.original_text then
    raise exception 'transcript source fields are immutable';
  end if;
  return new;
end;
$$;

create trigger protect_transcript_original_before_update
before update on public.meeting_transcripts
for each row execute function private.protect_transcript_original();

create trigger profiles_updated_at before update on public.profiles
for each row execute function private.set_updated_at();
create trigger teams_updated_at before update on public.teams
for each row execute function private.set_updated_at();
create trigger team_members_updated_at before update on public.team_members
for each row execute function private.set_updated_at();
create trigger meetings_updated_at before update on public.meetings
for each row execute function private.set_updated_at();
create trigger transcripts_updated_at before update on public.meeting_transcripts
for each row execute function private.set_updated_at();
create trigger notes_updated_at before update on public.meeting_notes
for each row execute function private.set_updated_at();
create trigger actions_updated_at before update on public.action_items
for each row execute function private.set_updated_at();
create trigger jobs_updated_at before update on public.processing_jobs
for each row execute function private.set_updated_at();

alter table public.profiles enable row level security;
alter table public.teams enable row level security;
alter table public.team_members enable row level security;
alter table public.meetings enable row level security;
alter table public.meeting_transcripts enable row level security;
alter table public.meeting_ai_runs enable row level security;
alter table public.meeting_notes enable row level security;
alter table public.action_items enable row level security;
alter table public.meeting_shares enable row level security;
alter table public.processing_jobs enable row level security;

create policy profiles_select_team on public.profiles for select to authenticated
using (auth.uid() = id or private.shares_active_team_with(id));
create policy profiles_update_self on public.profiles for update to authenticated
using (auth.uid() = id) with check (auth.uid() = id);

create policy teams_select_member on public.teams for select to authenticated
using (private.is_active_team_member(id));
create policy teams_insert_self on public.teams for insert to authenticated
with check (auth.uid() = created_by);
create policy teams_update_manager on public.teams for update to authenticated
using (private.is_team_manager(id)) with check (private.is_team_manager(id));
create policy team_members_select_member on public.team_members for select to authenticated
using (private.is_active_team_member(team_id));

create policy meetings_select_allowed on public.meetings for select to authenticated
using (deleted_at is null and private.can_view_meeting(id));
create policy meetings_insert_member on public.meetings for insert to authenticated
with check (created_by = auth.uid() and private.is_active_team_member(team_id));
create policy meetings_update_manager on public.meetings for update to authenticated
using (private.can_manage_meeting(id)) with check (private.can_manage_meeting(id));
create policy transcripts_select_viewer on public.meeting_transcripts for select to authenticated
using (private.can_view_meeting(meeting_id));
create policy transcripts_insert_manager on public.meeting_transcripts for insert to authenticated
with check (created_by = auth.uid() and private.can_manage_meeting(meeting_id));
create policy transcripts_update_manager on public.meeting_transcripts for update to authenticated
using (private.can_manage_meeting(meeting_id)) with check (private.can_manage_meeting(meeting_id));

create policy ai_runs_select_viewer on public.meeting_ai_runs for select to authenticated
using (private.can_view_meeting(meeting_id));
create policy notes_select_viewer on public.meeting_notes for select to authenticated
using (private.can_view_meeting(meeting_id));
create policy notes_write_manager on public.meeting_notes for all to authenticated
using (private.can_manage_meeting(meeting_id))
with check (updated_by = auth.uid() and private.can_manage_meeting(meeting_id));
create policy actions_select_viewer on public.action_items for select to authenticated
using (private.can_view_meeting(meeting_id));
create policy actions_write_manager on public.action_items for all to authenticated
using (private.can_manage_meeting(meeting_id))
with check (updated_by = auth.uid() and private.can_manage_meeting(meeting_id));

create policy shares_select_allowed on public.meeting_shares for select to authenticated
using (user_id = auth.uid() or private.can_manage_meeting(meeting_id));
create policy shares_insert_manager on public.meeting_shares for insert to authenticated
with check (
  shared_by = auth.uid()
  and user_id <> auth.uid()
  and private.can_manage_meeting(meeting_id)
  and private.is_active_team_member((select m.team_id from public.meetings m where m.id = meeting_id), user_id)
);
create policy shares_delete_manager on public.meeting_shares for delete to authenticated
using (private.can_manage_meeting(meeting_id));

create policy jobs_select_viewer on public.processing_jobs for select to authenticated
using (private.can_view_meeting(meeting_id));

revoke all on public.profiles from anon, authenticated;
revoke all on public.teams from anon, authenticated;
revoke all on public.team_members from anon, authenticated;
revoke all on public.meetings from anon, authenticated;
revoke all on public.meeting_transcripts from anon, authenticated;
revoke all on public.meeting_ai_runs from anon, authenticated;
revoke all on public.meeting_notes from anon, authenticated;
revoke all on public.action_items from anon, authenticated;
revoke all on public.meeting_shares from anon, authenticated;
revoke all on public.processing_jobs from anon, authenticated;

grant select on public.profiles to authenticated;
grant update(display_name, avatar_url) on public.profiles to authenticated;
grant select, insert on public.teams to authenticated;
grant update(name, description) on public.teams to authenticated;
grant select on public.team_members to authenticated;
grant select, insert on public.meetings to authenticated;
grant update(title, meeting_at, current_transcript_id, version, deleted_at)
  on public.meetings to authenticated;
grant select, insert, update on public.meeting_transcripts to authenticated;
grant select on public.meeting_ai_runs to authenticated;
grant select, insert, update, delete on public.meeting_notes to authenticated;
grant select, insert, update, delete on public.action_items to authenticated;
grant select, insert, delete on public.meeting_shares to authenticated;
grant select on public.processing_jobs to authenticated;

revoke all on all functions in schema private from public;
grant execute on function private.is_active_team_member(uuid, uuid) to authenticated;
grant execute on function private.is_team_manager(uuid, uuid) to authenticated;
grant execute on function private.can_view_meeting(uuid, uuid) to authenticated;
grant execute on function private.can_manage_meeting(uuid, uuid) to authenticated;
grant execute on function private.shares_active_team_with(uuid) to authenticated;

commit;
