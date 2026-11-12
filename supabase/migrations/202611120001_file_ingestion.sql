begin;

create type public.file_processing_status as enum (
  'pending_upload', 'uploaded', 'processing', 'succeeded', 'failed'
);

create table public.meeting_files (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  uploaded_by uuid not null references public.profiles(id) on delete restrict,
  storage_bucket text not null default 'meeting-files' check (storage_bucket = 'meeting-files'),
  storage_path text not null unique,
  original_name text not null check (char_length(original_name) between 1 and 255),
  mime_type text not null,
  size_bytes bigint not null check (size_bytes > 0 and size_bytes <= 26214400),
  sha256 text check (sha256 is null or sha256 ~ '^[0-9a-f]{64}$'),
  processing_status public.file_processing_status not null default 'pending_upload',
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index meeting_files_meeting_created_idx
  on public.meeting_files(meeting_id, created_at desc);
create unique index meeting_files_meeting_sha256_idx
  on public.meeting_files(meeting_id, sha256)
  where sha256 is not null;

alter table public.processing_jobs
  add column file_id uuid references public.meeting_files(id) on delete cascade;

alter table public.processing_jobs
  add constraint processing_jobs_file_scope_check check (
    (job_type = 'analyze' and file_id is null)
    or (job_type in ('extract', 'transcribe') and file_id is not null)
  );

create or replace function private.protect_meeting_file_identity()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.meeting_id is distinct from old.meeting_id
    or new.uploaded_by is distinct from old.uploaded_by
    or new.storage_bucket is distinct from old.storage_bucket
    or new.storage_path is distinct from old.storage_path
    or new.original_name is distinct from old.original_name
    or new.mime_type is distinct from old.mime_type
    or new.size_bytes is distinct from old.size_bytes then
    raise exception 'meeting file identity fields are immutable';
  end if;
  return new;
end;
$$;

create trigger protect_meeting_file_identity_before_update
before update on public.meeting_files
for each row execute function private.protect_meeting_file_identity();

create trigger meeting_files_updated_at
before update on public.meeting_files
for each row execute function private.set_updated_at();

alter table public.meeting_files enable row level security;

create policy meeting_files_select_viewer on public.meeting_files
for select to authenticated
using (private.can_view_meeting(meeting_id));

create policy meeting_files_insert_manager on public.meeting_files
for insert to authenticated
with check (
  uploaded_by = auth.uid()
  and private.can_manage_meeting(meeting_id)
);

create policy meeting_files_update_manager on public.meeting_files
for update to authenticated
using (private.can_manage_meeting(meeting_id))
with check (private.can_manage_meeting(meeting_id));

revoke all on public.meeting_files from anon, authenticated;
grant select, insert, update on public.meeting_files to authenticated;

grant select, insert, update, delete on public.meeting_files to service_role;
grant insert on public.meeting_transcripts to service_role;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'meeting-files',
  'meeting-files',
  false,
  26214400,
  array[
    'audio/mpeg', 'audio/mp4', 'audio/x-m4a', 'audio/wav', 'audio/x-wav',
    'text/plain', 'application/pdf'
  ]
)
on conflict (id) do update set
  public = false,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

create policy meeting_files_objects_select on storage.objects
for select to authenticated
using (
  bucket_id = 'meeting-files'
  and exists (
    select 1
    from public.meeting_files mf
    where mf.storage_bucket = bucket_id
      and mf.storage_path = name
      and private.can_view_meeting(mf.meeting_id)
  )
);

create policy meeting_files_objects_insert on storage.objects
for insert to authenticated
with check (
  bucket_id = 'meeting-files'
  and exists (
    select 1
    from public.meeting_files mf
    where mf.storage_bucket = bucket_id
      and mf.storage_path = name
      and mf.uploaded_by = auth.uid()
      and private.can_manage_meeting(mf.meeting_id)
  )
);

create policy meeting_files_objects_delete on storage.objects
for delete to authenticated
using (
  bucket_id = 'meeting-files'
  and exists (
    select 1
    from public.meeting_files mf
    where mf.storage_bucket = bucket_id
      and mf.storage_path = name
      and private.can_manage_meeting(mf.meeting_id)
  )
);

commit;
