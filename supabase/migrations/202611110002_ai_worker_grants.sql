-- MeetFlow AI background worker permissions.
-- The server verifies the user and meeting permissions before using the
-- server-only secret key. RLS bypass does not replace PostgreSQL table grants.

begin;

grant select, update on table public.meetings to service_role;
grant select on table public.meeting_transcripts to service_role;
grant select, insert on table public.meeting_ai_runs to service_role;
grant select, insert on table public.meeting_notes to service_role;
grant select, insert on table public.action_items to service_role;
grant select, insert, update on table public.processing_jobs to service_role;

commit;
