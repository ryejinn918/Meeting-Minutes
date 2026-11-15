-- In-app team invitations. This migration does not modify existing rows.
create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  type text not null check (type = 'team_invitation'),
  title text not null,
  body text not null,
  data jsonb not null default '{}'::jsonb,
  dedupe_key text unique,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists notifications_user_created_idx
  on public.notifications(user_id, created_at desc);
create index if not exists notifications_unread_idx
  on public.notifications(user_id, created_at desc) where read_at is null;

alter table public.notifications enable row level security;
create policy notifications_select_own on public.notifications
  for select to authenticated using (user_id = auth.uid());
create policy notifications_update_own on public.notifications
  for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

revoke all on public.notifications from anon, authenticated;
grant select on public.notifications to authenticated;
grant update(read_at) on public.notifications to authenticated;

-- Called with the inviter's JWT after the invitation row is created.
create or replace function public.create_team_invitation_notification(target_invitation_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public, private
as $$
declare
  invite public.team_invitations%rowtype;
  recipient_id uuid;
begin
  select * into invite from public.team_invitations where id = target_invitation_id;
  if invite.id is null or not private.is_team_manager(invite.team_id, auth.uid()) then
    raise exception 'invitation_not_allowed' using errcode = '42501';
  end if;

  select p.id into recipient_id
    from public.profiles p
   where lower(p.email) = invite.email_normalized;
  if recipient_id is null then
    return false;
  end if;

  insert into public.notifications(user_id, type, title, body, data, dedupe_key)
  values (
    recipient_id,
    'team_invitation',
    '팀 초대가 도착했어요',
    '새 팀 초대를 확인하고 참여 여부를 선택해 주세요.',
    jsonb_build_object('invitation_id', invite.id, 'team_id', invite.team_id),
    'team-invitation:' || invite.id
  ) on conflict (dedupe_key) do nothing;
  return true;
end;
$$;

create or replace function public.accept_team_invitation_notification(target_notification_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public, private
as $$
declare
  notification_row public.notifications%rowtype;
  invitation_row public.team_invitations%rowtype;
  team_id_value uuid;
begin
  select * into notification_row from public.notifications
   where id = target_notification_id and user_id = auth.uid();
  if notification_row.id is null or notification_row.type <> 'team_invitation' then
    raise exception 'notification_not_found' using errcode = 'P0002';
  end if;

  select ti.* into invitation_row
    from public.team_invitations ti
    join public.profiles p on lower(p.email) = ti.email_normalized
   where ti.id = (notification_row.data->>'invitation_id')::uuid
     and p.id = auth.uid()
     and ti.accepted_at is null
     and ti.expires_at > now();
  if invitation_row.id is null then
    raise exception 'invitation_invalid' using errcode = 'P0002';
  end if;

  insert into public.team_members(team_id, user_id, role, status)
  values (invitation_row.team_id, auth.uid(), invitation_row.role, 'active')
  on conflict (team_id, user_id) do update set role = excluded.role, status = 'active';
  update public.team_invitations set accepted_at = now() where id = invitation_row.id;
  update public.notifications set read_at = now() where id = notification_row.id;
  team_id_value := invitation_row.team_id;
  return team_id_value;
end;
$$;

create or replace function public.decline_team_invitation_notification(target_notification_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public, private
as $$
begin
  update public.notifications set read_at = now()
   where id = target_notification_id and user_id = auth.uid() and type = 'team_invitation';
  return found;
end;
$$;

revoke all on function public.create_team_invitation_notification(uuid) from public;
revoke all on function public.accept_team_invitation_notification(uuid) from public;
revoke all on function public.decline_team_invitation_notification(uuid) from public;
grant execute on function public.create_team_invitation_notification(uuid) to authenticated;
grant execute on function public.accept_team_invitation_notification(uuid) to authenticated;
grant execute on function public.decline_team_invitation_notification(uuid) to authenticated;
