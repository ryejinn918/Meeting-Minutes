begin;

alter table public.meeting_files
  drop constraint meeting_files_size_bytes_check;
alter table public.meeting_files
  add constraint meeting_files_size_bytes_check
  check (size_bytes > 0 and size_bytes <= 104857600);

update storage.buckets
set file_size_limit = 52428800
where id = 'meeting-files';

alter table public.processing_jobs
  add column usage jsonb not null default '{}'::jsonb
  check (jsonb_typeof(usage) = 'object');

create table public.processing_job_chunks (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.processing_jobs(id) on delete cascade,
  chunk_index integer not null check (chunk_index >= 0),
  chunk_sha256 text not null check (chunk_sha256 ~ '^[0-9a-f]{64}$'),
  start_seconds numeric(10, 3) not null check (start_seconds >= 0),
  end_seconds numeric(10, 3) not null check (end_seconds > start_seconds),
  transcript_text text not null check (length(btrim(transcript_text)) > 0),
  provider text not null,
  model text not null,
  usage jsonb not null default '{}'::jsonb check (jsonb_typeof(usage) = 'object'),
  created_at timestamptz not null default now(),
  unique (job_id, chunk_index)
);

create index processing_job_chunks_job_idx
  on public.processing_job_chunks(job_id, chunk_index);

alter table public.processing_job_chunks enable row level security;

revoke all on public.processing_job_chunks from anon, authenticated;
grant select, insert, update, delete on public.processing_job_chunks to service_role;

commit;
