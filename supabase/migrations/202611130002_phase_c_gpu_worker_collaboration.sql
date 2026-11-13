-- Phase C: explicit GPU transcription workers, invitations, and share receipts.
-- This migration is additive. It does not backfill, delete, or reassign existing data.

begin;

alter table public.meeting_files
  add column requested_stt_provider text not null default 'openai'
  check (requested_stt_provider in ('openai', 'whisperx'));

update storage.buckets set allowed_mime_types = array[
  'audio/mpeg','audio/mp4','audio/x-m4a','audio/wav','audio/x-wav','audio/webm','audio/ogg',
  'text/plain','application/pdf'
] where id = 'meeting-files';

alter table public.processing_jobs
  add column requested_provider text,
  add column worker_id uuid,
  add column claimed_at timestamptz,
  add column heartbeat_at timestamptz,
  add column lease_expires_at timestamptz,
  add column result_transcript_id uuid references public.meeting_transcripts(id) on delete set null;

create index processing_jobs_gpu_claim_idx
  on public.processing_jobs(status, created_at)
  where job_type = 'transcribe' and requested_provider = 'whisperx';

create table public.gpu_workers (
  id uuid primary key,
  name text not null check (char_length(name) between 1 and 100),
  last_seen_at timestamptz,
  current_job_id uuid references public.processing_jobs(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.gpu_workers enable row level security;
revoke all on public.gpu_workers from anon, authenticated;

create table public.team_invitations (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references public.teams(id) on delete cascade,
  email_normalized text not null,
  role public.team_role not null default 'member',
  token_hash text not null unique,
  expires_at timestamptz not null,
  accepted_at timestamptz,
  declined_at timestamptz,
  cancelled_at timestamptz,
  invited_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  check (email_normalized = lower(trim(email_normalized))),
  check (char_length(email_normalized) between 3 and 320),
  check (token_hash ~ '^[0-9a-f]{64}$'),
  check (expires_at > created_at),
  check (num_nonnulls(accepted_at, declined_at, cancelled_at) <= 1)
);
create unique index team_invitations_active_email_idx
  on public.team_invitations(team_id,email_normalized)
  where accepted_at is null and declined_at is null and cancelled_at is null;

create or replace function private.cancel_expired_team_invitation()
returns trigger
language plpgsql
security definer
set search_path = '' as $$
begin
  update public.team_invitations
  set cancelled_at = now()
  where team_id = new.team_id
    and email_normalized = new.email_normalized
    and accepted_at is null
    and declined_at is null
    and cancelled_at is null
    and expires_at <= now();
  return new;
end $$;

revoke all on function private.cancel_expired_team_invitation() from public, anon, authenticated;
create trigger team_invitations_cancel_expired_before_insert
before insert on public.team_invitations
for each row execute function private.cancel_expired_team_invitation();

alter table public.team_invitations enable row level security;
create policy invitations_manager_select on public.team_invitations for select to authenticated
using (private.is_team_manager(team_id));
create policy invitations_manager_insert on public.team_invitations for insert to authenticated
with check (
  invited_by=auth.uid() and private.is_team_manager(team_id)
);
revoke all on public.team_invitations from anon, authenticated;
grant select(id, team_id, email_normalized, role, expires_at, accepted_at, declined_at,
  cancelled_at, invited_by, created_at) on public.team_invitations to authenticated;
grant insert(id, team_id, email_normalized, role, token_hash, expires_at, invited_by)
  on public.team_invitations to authenticated;

alter table public.meeting_shares
  add column viewed_at timestamptz,
  add column updated_at timestamptz not null default now();

create or replace function public.claim_gpu_transcription_job(
  target_worker_id uuid, target_worker_name text, lease_seconds integer default 120
)
returns setof public.processing_jobs
language plpgsql security definer set search_path = '' as $$
declare claimed public.processing_jobs; expired_job record;
begin
  insert into public.gpu_workers(id, name, last_seen_at, updated_at)
  values (target_worker_id, target_worker_name, now(), now())
  on conflict (id) do update set name = excluded.name, last_seen_at = now(), updated_at = now();

  for expired_job in
    select id, file_id, worker_id from public.processing_jobs
    where job_type='transcribe' and requested_provider='whisperx' and status='processing'
      and attempt_count >= 2
      and coalesce(lease_expires_at, '-infinity'::timestamptz) < now()
    order by created_at for update skip locked limit 20
  loop
    update public.processing_jobs set status='failed', error_code='WORKER_LEASE_EXHAUSTED',
      error_message_safe='GPU 전사 작업이 중단되었습니다. 다시 시도해 주세요.',
      finished_at=now(), lease_expires_at=null, updated_at=now()
    where id=expired_job.id;
    update public.meeting_files set processing_status='failed',
      error_code='WORKER_LEASE_EXHAUSTED', updated_at=now()
    where id=expired_job.file_id;
    update public.gpu_workers set current_job_id=null, updated_at=now()
    where id=expired_job.worker_id and current_job_id=expired_job.id;
  end loop;

  select * into claimed from public.processing_jobs
  where job_type = 'transcribe' and requested_provider = 'whisperx'
    and attempt_count < 2
    and (status = 'queued' or (
      status = 'processing' and coalesce(lease_expires_at, '-infinity'::timestamptz) < now()
    ))
  order by created_at for update skip locked limit 1;
  if not found then return; end if;

  if claimed.worker_id is not null and claimed.worker_id is distinct from target_worker_id then
    update public.gpu_workers set current_job_id=null, updated_at=now()
    where id=claimed.worker_id and current_job_id=claimed.id;
  end if;

  update public.processing_jobs set status='processing', worker_id=target_worker_id,
    claimed_at=now(), heartbeat_at=now(),
    lease_expires_at=now() + make_interval(secs => greatest(30, least(lease_seconds, 600))),
    attempt_count=attempt_count + 1, started_at=coalesce(started_at, now()),
    finished_at=null, error_code=null, error_message_safe=null, updated_at=now()
  where id=claimed.id returning * into claimed;
  update public.gpu_workers set current_job_id=claimed.id where id=target_worker_id;
  return next claimed;
end $$;

create or replace function public.heartbeat_gpu_job(
  target_job_id uuid, target_worker_id uuid, lease_seconds integer default 120
)
returns boolean language plpgsql security definer set search_path = '' as $$
declare job_renewed boolean;
begin
  update public.processing_jobs set heartbeat_at=now(),
    lease_expires_at=now() + make_interval(secs => greatest(30, least(lease_seconds, 600))), updated_at=now()
  where id=target_job_id and worker_id=target_worker_id and status='processing'
    and lease_expires_at >= now();
  job_renewed := found;
  update public.gpu_workers set last_seen_at=now(), updated_at=now() where id=target_worker_id;
  return job_renewed;
end $$;

create or replace function public.complete_gpu_transcription_job(
  target_job_id uuid,
  target_worker_id uuid,
  target_text text,
  target_language text,
  target_model text,
  target_segments jsonb,
  target_usage jsonb
) returns uuid
language plpgsql security definer set search_path = '' as $$
declare
  job_row public.processing_jobs;
  file_row public.meeting_files;
  transcript_id uuid;
  segment_item jsonb;
  speaker_key text;
  speaker_id uuid;
  speaker_map jsonb := '{}'::jsonb;
  speaker_number integer := 0;
  segment_number integer := 0;
begin
  select * into job_row from public.processing_jobs
  where id=target_job_id for update;
  if not found or job_row.job_type <> 'transcribe' or job_row.requested_provider <> 'whisperx'
    or job_row.worker_id is distinct from target_worker_id then
    raise exception 'worker lease invalid' using errcode='55000';
  end if;
  if job_row.status = 'succeeded' and job_row.result_transcript_id is not null then
    return job_row.result_transcript_id;
  end if;
  if job_row.status <> 'processing' or job_row.lease_expires_at is null
    or job_row.lease_expires_at < now() then
    raise exception 'worker lease expired' using errcode='55000';
  end if;
  if nullif(btrim(target_text), '') is null or nullif(btrim(target_model), '') is null
    or jsonb_typeof(coalesce(target_segments, '[]'::jsonb)) <> 'array'
    or jsonb_typeof(coalesce(target_usage, '{}'::jsonb)) <> 'object' then
    raise exception 'worker result invalid' using errcode='22023';
  end if;

  select * into file_row from public.meeting_files
  where id=job_row.file_id and meeting_id=job_row.meeting_id for update;
  if not found then
    raise exception 'meeting file missing' using errcode='23503';
  end if;
  perform 1 from public.meetings
  where id=job_row.meeting_id and deleted_at is null for update;
  if not found then
    raise exception 'meeting missing' using errcode='23503';
  end if;

  transcript_id := gen_random_uuid();
  insert into public.meeting_transcripts(
    id, meeting_id, source, original_text, edited_text, language,
    stt_provider, stt_model, created_by
  ) values (
    transcript_id, job_row.meeting_id, 'audio', target_text, target_text,
    nullif(btrim(target_language), ''), 'whisperx', target_model, file_row.uploaded_by
  );

  for speaker_key in
    select item->>'speaker'
    from jsonb_array_elements(coalesce(target_segments, '[]'::jsonb)) with ordinality as entries(item, ordinal)
    where nullif(btrim(item->>'speaker'), '') is not null
    group by item->>'speaker'
    order by min(ordinal)
  loop
    speaker_number := speaker_number + 1;
    speaker_id := gen_random_uuid();
    insert into public.transcript_speakers(
      id, transcript_id, meeting_id, speaker_key, provider_label, display_name
    ) values (
      speaker_id, transcript_id, job_row.meeting_id, speaker_key, speaker_key,
      case when upper(speaker_key) = 'UNKNOWN' then '알 수 없는 화자'
           else '화자 ' || speaker_number::text end
    );
    speaker_map := speaker_map || jsonb_build_object(speaker_key, speaker_id::text);
  end loop;

  for segment_item in
    select value from jsonb_array_elements(coalesce(target_segments, '[]'::jsonb))
  loop
    speaker_key := segment_item->>'speaker';
    speaker_id := nullif(speaker_map->>speaker_key, '')::uuid;
    if speaker_id is null then
      raise exception 'segment speaker invalid' using errcode='22023';
    end if;
    insert into public.transcript_segments(
      transcript_id, meeting_id, speaker_id, segment_index,
      start_seconds, end_seconds, original_text
    ) values (
      transcript_id, job_row.meeting_id, speaker_id, segment_number,
      (segment_item->>'start')::numeric, (segment_item->>'end')::numeric,
      btrim(segment_item->>'text')
    );
    segment_number := segment_number + 1;
  end loop;

  update public.meetings set current_transcript_id=transcript_id,
    processing_status='draft', version=version+1, updated_at=now()
  where id=job_row.meeting_id;
  update public.meeting_files set processing_status='succeeded', error_code=null, updated_at=now()
  where id=file_row.id;
  update public.processing_jobs set status='succeeded', usage=coalesce(target_usage, '{}'::jsonb),
    result_transcript_id=transcript_id, finished_at=now(), lease_expires_at=null,
    error_code=null, error_message_safe=null, updated_at=now()
  where id=job_row.id;
  update public.gpu_workers set current_job_id=null, last_seen_at=now(), updated_at=now()
  where id=target_worker_id and current_job_id=job_row.id;
  return transcript_id;
end $$;

create or replace function public.fail_gpu_transcription_job(
  target_job_id uuid, target_worker_id uuid, target_error_code text, target_error_message text
) returns boolean
language plpgsql security definer set search_path = '' as $$
declare job_row public.processing_jobs;
begin
  select * into job_row from public.processing_jobs where id=target_job_id for update;
  if not found or job_row.worker_id is distinct from target_worker_id then
    return false;
  end if;
  if job_row.status = 'failed' then return true; end if;
  if job_row.status <> 'processing' or job_row.lease_expires_at is null
    or job_row.lease_expires_at < now() then
    return false;
  end if;
  update public.meeting_files set processing_status='failed', error_code=target_error_code,
    updated_at=now() where id=job_row.file_id;
  update public.processing_jobs set status='failed', error_code=target_error_code,
    error_message_safe=target_error_message, finished_at=now(), lease_expires_at=null,
    updated_at=now() where id=job_row.id;
  update public.gpu_workers set current_job_id=null, last_seen_at=now(), updated_at=now()
  where id=target_worker_id and current_job_id=job_row.id;
  return true;
end $$;

revoke all on function public.claim_gpu_transcription_job(uuid,text,integer) from public, anon, authenticated;
revoke all on function public.heartbeat_gpu_job(uuid,uuid,integer) from public, anon, authenticated;
revoke all on function public.complete_gpu_transcription_job(uuid,uuid,text,text,text,jsonb,jsonb)
  from public, anon, authenticated;
revoke all on function public.fail_gpu_transcription_job(uuid,uuid,text,text)
  from public, anon, authenticated;
grant execute on function public.claim_gpu_transcription_job(uuid,text,integer) to service_role;
grant execute on function public.heartbeat_gpu_job(uuid,uuid,integer) to service_role;
grant execute on function public.complete_gpu_transcription_job(uuid,uuid,text,text,text,jsonb,jsonb)
  to service_role;
grant execute on function public.fail_gpu_transcription_job(uuid,uuid,text,text) to service_role;

create or replace function public.replace_meeting_shares(
  target_meeting_id uuid, target_shares jsonb
) returns void language plpgsql security definer set search_path = '' as $$
declare target_team_id uuid; item jsonb; target_user_id uuid;
begin
  if auth.uid() is null or not private.can_manage_meeting(target_meeting_id) then
    raise exception 'meeting share denied' using errcode = '42501';
  end if;
  select team_id into target_team_id from public.meetings
  where id=target_meeting_id and deleted_at is null;
  if target_team_id is null or jsonb_typeof(coalesce(target_shares, '[]'::jsonb)) <> 'array'
    or jsonb_array_length(coalesce(target_shares, '[]'::jsonb)) > 500 then
    raise exception 'invalid share request' using errcode = '22023';
  end if;
  delete from public.meeting_shares where meeting_id=target_meeting_id;
  for item in select value from jsonb_array_elements(coalesce(target_shares, '[]'::jsonb)) loop
    target_user_id := (item->>'user_id')::uuid;
    if target_user_id = auth.uid() or not private.is_active_team_member(target_team_id, target_user_id) then
      raise exception 'invalid share target' using errcode = '42501';
    end if;
    insert into public.meeting_shares(meeting_id,user_id,shared_by,can_edit)
    values(target_meeting_id,target_user_id,auth.uid(),false);
  end loop;
end $$;
revoke all on function public.replace_meeting_shares(uuid,jsonb) from public, anon, authenticated;
grant execute on function public.replace_meeting_shares(uuid,jsonb) to authenticated;

create or replace function public.accept_team_invitation(target_token_hash text)
returns uuid language plpgsql security definer set search_path = '' as $$
declare invitation public.team_invitations; target_email text; team_row public.teams;
begin
  if auth.uid() is null then raise exception 'authentication required' using errcode='42501'; end if;
  select lower(email) into target_email from auth.users where id=auth.uid();
  select * into invitation from public.team_invitations
  where token_hash=target_token_hash and accepted_at is null and declined_at is null
    and cancelled_at is null and expires_at > now() for update;
  if not found or invitation.email_normalized <> target_email then
    raise exception 'invitation invalid' using errcode='42501';
  end if;
  select * into team_row from public.teams where id=invitation.team_id;
  if team_row.organization_id is not null then
    insert into public.organization_members(organization_id,user_id,role,status)
    values(team_row.organization_id,auth.uid(),'member','active')
    on conflict(organization_id,user_id) do nothing;
    if not exists (
      select 1 from public.organization_members
      where organization_id=team_row.organization_id and user_id=auth.uid() and status='active'
    ) then
      raise exception 'organization membership inactive' using errcode='42501';
    end if;
    insert into public.department_members(department_id,user_id,role,status)
    values(team_row.department_id,auth.uid(),'member','active')
    on conflict(department_id,user_id) do nothing;
    if not exists (
      select 1 from public.department_members
      where department_id=team_row.department_id and user_id=auth.uid() and status='active'
    ) then
      raise exception 'department membership inactive' using errcode='42501';
    end if;
  end if;
  insert into public.team_members(team_id,user_id,role,status)
  values(invitation.team_id,auth.uid(),invitation.role,'active')
  on conflict(team_id,user_id) do update set status='active';
  update public.team_invitations set accepted_at=now() where id=invitation.id;
  return invitation.team_id;
end $$;
revoke all on function public.accept_team_invitation(text) from public, anon, authenticated;
grant execute on function public.accept_team_invitation(text) to authenticated;

create or replace function public.cancel_team_invitation(
  target_team_id uuid, target_invitation_id uuid
) returns boolean
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not private.is_team_manager(target_team_id) then
    raise exception 'invitation cancel denied' using errcode='42501';
  end if;
  update public.team_invitations set cancelled_at=now()
  where id=target_invitation_id and team_id=target_team_id
    and accepted_at is null and declined_at is null and cancelled_at is null;
  return found;
end $$;

create or replace function public.decline_team_invitation(target_token_hash text)
returns boolean
language plpgsql security definer set search_path = '' as $$
declare target_email text;
begin
  if auth.uid() is null then
    raise exception 'authentication required' using errcode='42501';
  end if;
  select lower(email) into target_email from auth.users where id=auth.uid();
  update public.team_invitations set declined_at=now()
  where token_hash=target_token_hash and email_normalized=target_email
    and accepted_at is null and declined_at is null and cancelled_at is null
    and expires_at > now();
  return found;
end $$;

revoke all on function public.cancel_team_invitation(uuid,uuid) from public, anon, authenticated;
revoke all on function public.decline_team_invitation(text) from public, anon, authenticated;
grant execute on function public.cancel_team_invitation(uuid,uuid) to authenticated;
grant execute on function public.decline_team_invitation(text) to authenticated;

create policy shares_mark_viewed on public.meeting_shares for update to authenticated
using (user_id = auth.uid()) with check (user_id = auth.uid());
grant update(viewed_at) on public.meeting_shares to authenticated;

create trigger meeting_shares_updated_at before update on public.meeting_shares
for each row execute function private.set_updated_at();

create trigger gpu_workers_updated_at before update on public.gpu_workers
for each row execute function private.set_updated_at();

commit;
