begin;

create type public.organization_role as enum ('org_admin', 'member');
create type public.department_role as enum ('department_admin', 'member');

create table public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 2 and 100),
  description text not null default '',
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.organization_members (
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role public.organization_role not null default 'member',
  status public.member_status not null default 'active',
  joined_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (organization_id, user_id)
);

create table public.departments (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null check (char_length(name) between 2 and 100),
  description text not null default '',
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, organization_id),
  unique (organization_id, name)
);

create table public.department_members (
  department_id uuid not null references public.departments(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role public.department_role not null default 'member',
  status public.member_status not null default 'active',
  joined_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (department_id, user_id)
);

alter table public.teams
  add column organization_id uuid references public.organizations(id) on delete restrict,
  add column department_id uuid,
  add constraint teams_scope_pair_check check (
    (organization_id is null and department_id is null)
    or (organization_id is not null and department_id is not null)
  ),
  add constraint teams_department_scope_fk
    foreign key (department_id, organization_id)
    references public.departments(id, organization_id) on delete restrict;

create index organization_members_user_status_idx
  on public.organization_members(user_id, status);
create index departments_organization_name_idx
  on public.departments(organization_id, name);
create index department_members_user_status_idx
  on public.department_members(user_id, status);
create index teams_organization_department_idx
  on public.teams(organization_id, department_id);

create or replace function private.is_active_organization_member(
  target_organization_id uuid,
  target_user_id uuid default auth.uid()
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.organization_members om
    where om.organization_id = target_organization_id
      and om.user_id = target_user_id
      and om.status = 'active'
  );
$$;

create or replace function private.is_organization_admin(
  target_organization_id uuid,
  target_user_id uuid default auth.uid()
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.organization_members om
    where om.organization_id = target_organization_id
      and om.user_id = target_user_id
      and om.status = 'active'
      and om.role = 'org_admin'
  );
$$;

create or replace function private.is_active_department_member(
  target_department_id uuid,
  target_user_id uuid default auth.uid()
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.department_members dm
    where dm.department_id = target_department_id
      and dm.user_id = target_user_id
      and dm.status = 'active'
  );
$$;

create or replace function private.is_department_admin(
  target_department_id uuid,
  target_user_id uuid default auth.uid()
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.department_members dm
    where dm.department_id = target_department_id
      and dm.user_id = target_user_id
      and dm.status = 'active'
      and dm.role = 'department_admin'
  );
$$;

create or replace function private.handle_new_organization()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.organization_members(organization_id, user_id, role, status)
  values (new.id, new.created_by, 'org_admin', 'active');
  return new;
end;
$$;

create trigger on_organization_created
after insert on public.organizations
for each row execute function private.handle_new_organization();

create or replace function private.handle_new_department()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.department_members(department_id, user_id, role, status)
  values (new.id, new.created_by, 'department_admin', 'active');
  return new;
end;
$$;

create trigger on_department_created
after insert on public.departments
for each row execute function private.handle_new_department();

create trigger organizations_updated_at before update on public.organizations
for each row execute function private.set_updated_at();
create trigger organization_members_updated_at before update on public.organization_members
for each row execute function private.set_updated_at();
create trigger departments_updated_at before update on public.departments
for each row execute function private.set_updated_at();
create trigger department_members_updated_at before update on public.department_members
for each row execute function private.set_updated_at();

alter table public.organizations enable row level security;
alter table public.organization_members enable row level security;
alter table public.departments enable row level security;
alter table public.department_members enable row level security;

create policy organizations_select_member on public.organizations for select to authenticated
using (private.is_active_organization_member(id));
create policy organizations_insert_self on public.organizations for insert to authenticated
with check (created_by = auth.uid());
create policy organizations_update_admin on public.organizations for update to authenticated
using (private.is_organization_admin(id)) with check (private.is_organization_admin(id));

create policy organization_members_select_member on public.organization_members for select to authenticated
using (private.is_active_organization_member(organization_id));

create policy departments_select_org_member on public.departments for select to authenticated
using (private.is_active_organization_member(organization_id));
create policy departments_insert_org_admin on public.departments for insert to authenticated
with check (created_by = auth.uid() and private.is_organization_admin(organization_id));
create policy departments_update_manager on public.departments for update to authenticated
using (
  private.is_organization_admin(organization_id)
  or private.is_department_admin(id)
)
with check (
  private.is_organization_admin(organization_id)
  or private.is_department_admin(id)
);

create policy department_members_select_org_member on public.department_members for select to authenticated
using (
  exists (
    select 1 from public.departments d
    where d.id = department_id
      and private.is_active_organization_member(d.organization_id)
  )
);

drop policy teams_insert_self on public.teams;
create policy teams_insert_scoped on public.teams for insert to authenticated
with check (
  created_by = auth.uid()
  and (
    (organization_id is null and department_id is null)
    or (
      organization_id is not null
      and department_id is not null
      and (
        private.is_organization_admin(organization_id)
        or private.is_department_admin(department_id)
      )
    )
  )
);

revoke all on public.organizations from anon, authenticated;
revoke all on public.organization_members from anon, authenticated;
revoke all on public.departments from anon, authenticated;
revoke all on public.department_members from anon, authenticated;
grant select, insert on public.organizations to authenticated;
grant update(name, description) on public.organizations to authenticated;
grant select on public.organization_members to authenticated;
grant select, insert on public.departments to authenticated;
grant update(name, description) on public.departments to authenticated;
grant select on public.department_members to authenticated;

grant usage on schema private to authenticated;
revoke all on function private.is_active_organization_member(uuid, uuid) from public;
revoke all on function private.is_organization_admin(uuid, uuid) from public;
revoke all on function private.is_active_department_member(uuid, uuid) from public;
revoke all on function private.is_department_admin(uuid, uuid) from public;
grant execute on function private.is_active_organization_member(uuid, uuid) to authenticated;
grant execute on function private.is_organization_admin(uuid, uuid) to authenticated;
grant execute on function private.is_active_department_member(uuid, uuid) to authenticated;
grant execute on function private.is_department_admin(uuid, uuid) to authenticated;

create or replace function public.soft_delete_meeting(
  target_meeting_id uuid,
  expected_version integer
)
returns text
language plpgsql
security invoker
set search_path = ''
as $$
declare
  current_version integer;
  affected_rows integer;
begin
  select m.version into current_version
  from public.meetings m
  where m.id = target_meeting_id and m.deleted_at is null;

  if current_version is null then
    return 'not_found';
  end if;
  if not private.can_manage_meeting(target_meeting_id) then
    return 'forbidden';
  end if;
  if current_version <> expected_version then
    return 'version_conflict';
  end if;
  if exists (
    select 1 from public.processing_jobs pj
    where pj.meeting_id = target_meeting_id
      and pj.status in ('queued', 'processing')
  ) then
    return 'active_job';
  end if;

  update public.meetings
  set deleted_at = now(), version = version + 1
  where id = target_meeting_id
    and version = expected_version
    and deleted_at is null;
  get diagnostics affected_rows = row_count;

  if affected_rows <> 1 then
    return 'version_conflict';
  end if;
  return 'deleted';
end;
$$;

revoke all on function public.soft_delete_meeting(uuid, integer) from public;
grant execute on function public.soft_delete_meeting(uuid, integer) to authenticated;

commit;
