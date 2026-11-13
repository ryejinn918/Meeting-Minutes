-- Phase B follow-up: explicit speaker confirmation and review approval state.
-- Additive only; existing transcript and meeting rows remain unchanged.

alter table public.meetings
  add column if not exists review_status text not null default 'draft'
    check (review_status in ('draft', 'review_required', 'approved', 'rejected')),
  add column if not exists approved_at timestamptz,
  add column if not exists approved_by uuid references public.profiles(id) on delete set null,
  add column if not exists approval_version integer;

alter table public.transcript_speakers
  add column if not exists candidate_user_id uuid references public.profiles(id) on delete set null,
  add column if not exists candidate_confidence numeric(5,4)
    check (candidate_confidence is null or (candidate_confidence >= 0 and candidate_confidence <= 1)),
  add column if not exists candidate_reason text not null default '',
  add column if not exists confirmed_at timestamptz,
  add column if not exists confirmed_by uuid references public.profiles(id) on delete set null;

create table if not exists public.meeting_reviews (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  status text not null check (status in ('draft', 'review_required', 'approved', 'rejected')),
  note text not null default '',
  version integer not null,
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now()
);

create table if not exists public.team_voice_profiles (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references public.teams(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  label text not null default '',
  consented_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (team_id, user_id)
);

alter table public.team_voice_profiles enable row level security;
create or replace function private.can_manage_team(
  target_team_id uuid, target_user_id uuid default auth.uid()
)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.team_members tm
    where tm.team_id = target_team_id and tm.user_id = target_user_id
      and tm.status = 'active' and tm.role in ('owner', 'admin')
  );
$$;
revoke all on function private.can_manage_team(uuid, uuid) from public;
grant execute on function private.can_manage_team(uuid, uuid) to authenticated;
create policy team_voice_profiles_select_member on public.team_voice_profiles
  for select to authenticated using (private.is_active_team_member(team_id));
create policy team_voice_profiles_write_manager on public.team_voice_profiles
  for all to authenticated
  using (private.can_manage_team(team_id) or user_id = auth.uid())
  with check (
    private.is_active_team_member(team_id, user_id)
    and (private.can_manage_team(team_id) or user_id = auth.uid())
  );
revoke all on public.team_voice_profiles from anon, authenticated;
grant select, insert, update on public.team_voice_profiles to authenticated;

create index if not exists meeting_reviews_meeting_created_idx
  on public.meeting_reviews(meeting_id, created_at desc);

alter table public.meeting_reviews enable row level security;
create policy meeting_reviews_select_viewer on public.meeting_reviews
  for select to authenticated using (private.can_view_meeting(meeting_id));
create policy meeting_reviews_insert_manager on public.meeting_reviews
  for insert to authenticated
  with check (created_by = auth.uid() and private.can_manage_meeting(meeting_id));

revoke all on public.meeting_reviews from anon, authenticated;
grant select, insert on public.meeting_reviews to authenticated;
grant update(review_status, approved_at, approved_by, approval_version) on public.meetings to authenticated;
grant select, update(candidate_user_id, candidate_confidence, candidate_reason, confirmed_at, confirmed_by)
  on public.transcript_speakers to authenticated;

create policy transcript_speakers_candidate_update_manager on public.transcript_speakers
  for update to authenticated
  using (exists (
    select 1 from public.meeting_transcripts mt
    where mt.id = transcript_speakers.transcript_id
      and private.can_manage_meeting(mt.meeting_id)
  ))
  with check (exists (
    select 1 from public.meeting_transcripts mt
    where mt.id = transcript_speakers.transcript_id
      and private.can_manage_meeting(mt.meeting_id)
  ));
