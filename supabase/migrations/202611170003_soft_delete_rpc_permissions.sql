begin;

-- Keep soft deletion protected by the existing meetings RLS policies while
-- making the RPC's authenticated execution privileges explicit. This is
-- intentionally idempotent and does not alter data or disable RLS.
grant usage on schema public to authenticated;
grant usage on schema private to authenticated;
grant execute on function private.can_manage_meeting(uuid, uuid) to authenticated;
grant execute on function public.soft_delete_meeting(uuid, integer) to authenticated;
grant select on public.meetings to authenticated;
grant update(version, deleted_at) on public.meetings to authenticated;
grant select on public.processing_jobs to authenticated;

commit;
