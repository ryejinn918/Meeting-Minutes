begin;

create extension if not exists pgtap with schema extensions;
select plan(5);

insert into auth.users (
  id, aud, role, email, encrypted_password, email_confirmed_at,
  raw_app_meta_data, raw_user_meta_data, created_at, updated_at
) values
  ('11111111-1111-4111-8111-111111111111', 'authenticated', 'authenticated', 'owner@example.com', '', now(), '{}'::jsonb, '{"display_name":"Owner"}'::jsonb, now(), now()),
  ('22222222-2222-4222-8222-222222222222', 'authenticated', 'authenticated', 'member@example.com', '', now(), '{}'::jsonb, '{"display_name":"Member"}'::jsonb, now(), now());

insert into public.teams (id, name, created_by)
values ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'RLS Test Team', '11111111-1111-4111-8111-111111111111');

insert into public.team_members (team_id, user_id, role)
values ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '22222222-2222-4222-8222-222222222222', 'member');

insert into public.meetings (id, team_id, title, meeting_at, source_type, created_by)
values (
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'Private Meeting',
  now(),
  'direct',
  '11111111-1111-4111-8111-111111111111'
);

set local role authenticated;
select set_config('request.jwt.claim.sub', '11111111-1111-4111-8111-111111111111', true);
select set_config('request.jwt.claim.role', 'authenticated', true);
select results_eq(
  $$select count(*)::bigint from public.meetings where id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'$$,
  array[1::bigint],
  'owner can view own meeting'
);

set local role postgres;
select set_config('request.jwt.claim.sub', '22222222-2222-4222-8222-222222222222', true);
set local role authenticated;
select results_eq(
  $$select count(*)::bigint from public.meetings where id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'$$,
  array[0::bigint],
  'unshared regular member cannot view meeting'
);

set local role postgres;
insert into public.meeting_shares (meeting_id, user_id, shared_by)
values (
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  '22222222-2222-4222-8222-222222222222',
  '11111111-1111-4111-8111-111111111111'
);
select set_config('request.jwt.claim.sub', '22222222-2222-4222-8222-222222222222', true);
set local role authenticated;
select results_eq(
  $$select count(*)::bigint from public.meetings where id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'$$,
  array[1::bigint],
  'shared regular member can view meeting'
);
select results_eq(
  $$update public.meetings set title = 'Blocked' where id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb' returning id$$,
  array[]::uuid[],
  'shared regular member remains read only'
);

set local role postgres;
select set_config('request.jwt.claim.sub', '11111111-1111-4111-8111-111111111111', true);
set local role authenticated;
select throws_ok(
  $$delete from public.meetings where id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'$$,
  '42501',
  'permission denied for table meetings',
  'authenticated users cannot hard delete meetings'
);

select * from finish();
rollback;
