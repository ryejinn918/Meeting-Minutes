begin;

alter table public.processing_job_chunks
  add column segments jsonb not null default '[]'::jsonb
  check (jsonb_typeof(segments) = 'array');

create table public.transcript_speakers (
  id uuid primary key default gen_random_uuid(),
  transcript_id uuid not null references public.meeting_transcripts(id) on delete cascade,
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  speaker_key text not null check (char_length(speaker_key) between 1 and 200),
  provider_label text not null check (char_length(provider_label) between 1 and 100),
  display_name text not null check (char_length(display_name) between 1 and 100),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (transcript_id, speaker_key)
);

create table public.transcript_segments (
  id uuid primary key default gen_random_uuid(),
  transcript_id uuid not null references public.meeting_transcripts(id) on delete cascade,
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  speaker_id uuid not null references public.transcript_speakers(id) on delete cascade,
  segment_index integer not null check (segment_index >= 0),
  start_seconds numeric(12, 3) not null check (start_seconds >= 0),
  end_seconds numeric(12, 3) not null check (end_seconds > start_seconds),
  original_text text not null check (length(btrim(original_text)) > 0),
  created_at timestamptz not null default now(),
  unique (transcript_id, segment_index)
);

create index transcript_speakers_transcript_idx
  on public.transcript_speakers(transcript_id);
create index transcript_segments_transcript_order_idx
  on public.transcript_segments(transcript_id, segment_index);

create trigger transcript_speakers_set_updated_at
before update on public.transcript_speakers
for each row execute function private.set_updated_at();

alter table public.transcript_speakers enable row level security;
alter table public.transcript_segments enable row level security;

create policy transcript_speakers_select_viewer
on public.transcript_speakers for select to authenticated
using (private.can_view_meeting(meeting_id));
create policy transcript_speakers_update_manager
on public.transcript_speakers for update to authenticated
using (private.can_manage_meeting(meeting_id))
with check (private.can_manage_meeting(meeting_id));
create policy transcript_segments_select_viewer
on public.transcript_segments for select to authenticated
using (private.can_view_meeting(meeting_id));

revoke all on public.transcript_speakers from anon, authenticated;
revoke all on public.transcript_segments from anon, authenticated;
grant select on public.transcript_speakers to authenticated;
grant update(display_name) on public.transcript_speakers to authenticated;
grant select on public.transcript_segments to authenticated;

grant select, insert, update on public.transcript_speakers to service_role;
grant select, insert on public.transcript_segments to service_role;

commit;
