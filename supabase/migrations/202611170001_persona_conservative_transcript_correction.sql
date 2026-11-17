-- Persona-driven, conservative transcript correction.
-- Existing glossary data is intentionally preserved for backward compatibility;
-- the application no longer uses it for automatic correction.
alter table public.meetings
  add column if not exists correction_persona text not null default 'general';

alter table public.meetings
  add constraint meetings_correction_persona_length
  check (char_length(correction_persona) between 1 and 80);

grant update(correction_persona) on public.meetings to authenticated;
