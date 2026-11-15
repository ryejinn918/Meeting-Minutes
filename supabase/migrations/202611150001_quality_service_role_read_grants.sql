-- Allow the server-side analysis worker to read optional quality context.
-- AuthorizationService still checks the meeting and team before these reads.
-- No write privileges or RLS changes are introduced.
begin;

grant select on table public.meeting_templates to service_role;
grant select on table public.glossary_terms to service_role;

commit;
