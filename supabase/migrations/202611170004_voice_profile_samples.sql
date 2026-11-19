-- Additive voice-profile sample metadata. The sample remains private in Storage.
alter table public.team_voice_profiles
  add column if not exists sample_object_path text,
  add column if not exists sample_mime_type text,
  add column if not exists sample_size_bytes bigint,
  add column if not exists sample_sha256 text,
  add column if not exists sample_uploaded_at timestamptz;

alter table public.team_voice_profiles
  add constraint team_voice_profiles_sample_size_check
  check (sample_size_bytes is null or sample_size_bytes between 1 and 104857600),
  add constraint team_voice_profiles_sample_sha256_check
  check (sample_sha256 is null or sample_sha256 ~ '^[0-9a-f]{64}$');

create index if not exists team_voice_profiles_team_active_idx
  on public.team_voice_profiles(team_id, revoked_at);

grant select, update(
  label, consented_at, revoked_at, sample_object_path, sample_mime_type,
  sample_size_bytes, sample_sha256, sample_uploaded_at
) on public.team_voice_profiles to authenticated;
