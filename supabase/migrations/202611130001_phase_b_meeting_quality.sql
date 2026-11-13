begin;

alter table public.meetings
  add column topic text not null default '' check (char_length(topic) <= 500),
  add column location text not null default '' check (char_length(location) <= 300),
  add column meeting_type text not null default 'general'
    check (meeting_type in ('general', 'project', 'interview', 'workshop')),
  add column purpose text not null default '' check (char_length(purpose) <= 1000),
  add column project_name text not null default '' check (char_length(project_name) <= 300),
  add column metadata_confirmed_at timestamptz;

alter table public.meeting_transcripts
  add column corrected_text text;

create table public.meeting_templates (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references public.organizations(id) on delete cascade,
  department_id uuid,
  team_id uuid references public.teams(id) on delete cascade,
  name text not null check (char_length(name) between 2 and 100),
  description text not null default '' check (char_length(description) <= 500),
  meeting_type text not null check (meeting_type in ('general', 'project', 'interview', 'workshop')),
  sections jsonb not null check (jsonb_typeof(sections) = 'array'),
  writing_rules text not null default '' check (char_length(writing_rules) <= 3000),
  is_default boolean not null default false,
  version integer not null default 1 check (version > 0),
  is_active boolean not null default true,
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint meeting_templates_scope_check check (
    (organization_id is not null or team_id is not null)
    and (department_id is null or organization_id is not null)
  ),
  constraint meeting_templates_department_scope_fk
    foreign key (department_id, organization_id)
    references public.departments(id, organization_id) on delete cascade
);

alter table public.meetings
  add column template_id uuid references public.meeting_templates(id) on delete set null;

create table public.meeting_template_versions (
  id uuid primary key default gen_random_uuid(),
  template_id uuid not null references public.meeting_templates(id) on delete cascade,
  version integer not null check (version > 0),
  snapshot jsonb not null check (jsonb_typeof(snapshot) = 'object'),
  changed_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  unique (template_id, version)
);

create or replace function private.capture_meeting_template_version()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.meeting_template_versions(template_id, version, snapshot, changed_by)
  values (
    old.id,
    old.version,
    to_jsonb(old) - 'created_at' - 'updated_at',
    auth.uid()
  )
  on conflict (template_id, version) do nothing;
  return new;
end;
$$;

create trigger meeting_templates_capture_version before update on public.meeting_templates
for each row execute function private.capture_meeting_template_version();

create table public.glossary_terms (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references public.organizations(id) on delete cascade,
  department_id uuid,
  team_id uuid references public.teams(id) on delete cascade,
  term text not null check (char_length(term) between 1 and 200),
  preferred_term text not null check (char_length(preferred_term) between 1 and 200),
  aliases jsonb not null default '[]'::jsonb check (jsonb_typeof(aliases) = 'array'),
  description text not null default '' check (char_length(description) <= 1000),
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint glossary_terms_scope_check check (
    (organization_id is not null or team_id is not null)
    and (department_id is null or organization_id is not null)
  ),
  constraint glossary_terms_department_scope_fk
    foreign key (department_id, organization_id)
    references public.departments(id, organization_id) on delete cascade
);

create table public.meeting_attendees (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  user_id uuid references public.profiles(id) on delete restrict,
  external_name text,
  external_organization text,
  created_at timestamptz not null default now(),
  constraint meeting_attendees_identity_check check (
    (user_id is not null and external_name is null)
    or (user_id is null and char_length(btrim(external_name)) between 1 and 100)
  ),
  unique (meeting_id, user_id)
);

create table public.transcript_corrections (
  id uuid primary key default gen_random_uuid(),
  transcript_id uuid not null references public.meeting_transcripts(id) on delete cascade,
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  original_text text not null,
  corrected_text text not null,
  changes jsonb not null default '[]'::jsonb check (jsonb_typeof(changes) = 'array'),
  uncertainties jsonb not null default '[]'::jsonb check (jsonb_typeof(uncertainties) = 'array'),
  context_snapshot jsonb not null default '{}'::jsonb check (jsonb_typeof(context_snapshot) = 'object'),
  provider text not null,
  model text not null,
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now()
);

create table public.meeting_questions (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  category text not null check (category in ('decision', 'assignee', 'due_date', 'number', 'name', 'speaker', 'other')),
  question text not null check (char_length(question) between 1 and 1000),
  evidence text check (char_length(evidence) <= 1000),
  answer text check (char_length(answer) <= 2000),
  status text not null default 'pending' check (status in ('pending', 'answered', 'dismissed')),
  created_by uuid not null references public.profiles(id) on delete restrict,
  answered_by uuid references public.profiles(id) on delete restrict,
  answered_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.transcript_speaker_edit_batches (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  transcript_id uuid not null references public.meeting_transcripts(id) on delete cascade,
  changes jsonb not null check (jsonb_typeof(changes) = 'array'),
  created_by uuid not null references public.profiles(id) on delete restrict,
  reverted_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.transcript_segment_speaker_edits (
  segment_id uuid primary key references public.transcript_segments(id) on delete cascade,
  meeting_id uuid not null references public.meetings(id) on delete cascade,
  transcript_id uuid not null references public.meeting_transcripts(id) on delete cascade,
  speaker_id uuid not null references public.transcript_speakers(id) on delete cascade,
  batch_id uuid not null references public.transcript_speaker_edit_batches(id) on delete cascade,
  updated_by uuid not null references public.profiles(id) on delete restrict,
  updated_at timestamptz not null default now()
);

create index meeting_templates_scope_idx on public.meeting_templates(organization_id, department_id, team_id) where is_active;
create index glossary_terms_scope_idx on public.glossary_terms(organization_id, department_id, team_id);
create index meeting_attendees_meeting_idx on public.meeting_attendees(meeting_id);
create index transcript_corrections_transcript_idx on public.transcript_corrections(transcript_id, created_at desc);
create index meeting_questions_meeting_status_idx on public.meeting_questions(meeting_id, status, created_at);
create index transcript_speaker_edit_batches_meeting_idx on public.transcript_speaker_edit_batches(meeting_id, created_at desc);
create index transcript_segment_speaker_edits_transcript_idx on public.transcript_segment_speaker_edits(transcript_id);

create trigger meeting_templates_updated_at before update on public.meeting_templates
for each row execute function private.set_updated_at();
create trigger glossary_terms_updated_at before update on public.glossary_terms
for each row execute function private.set_updated_at();
create trigger meeting_questions_updated_at before update on public.meeting_questions
for each row execute function private.set_updated_at();

create or replace function private.can_view_quality_scope(
  target_organization_id uuid,
  target_department_id uuid,
  target_team_id uuid,
  target_user_id uuid default auth.uid()
)
returns boolean language sql stable security definer set search_path = '' as $$
  select case
    when target_team_id is not null then
      private.is_active_team_member(target_team_id, target_user_id)
      or (
        target_organization_id is not null
        and private.is_organization_admin(target_organization_id, target_user_id)
      )
    when target_department_id is not null then
      private.is_active_department_member(target_department_id, target_user_id)
      or private.is_organization_admin(target_organization_id, target_user_id)
      or exists (
        select 1
        from public.teams t
        join public.team_members tm on tm.team_id = t.id
        where t.department_id = target_department_id
          and tm.user_id = target_user_id
          and tm.status = 'active'
      )
    else
      target_organization_id is not null
      and private.is_active_organization_member(target_organization_id, target_user_id)
  end;
$$;

create or replace function private.can_manage_quality_scope(
  target_organization_id uuid,
  target_department_id uuid,
  target_team_id uuid,
  target_user_id uuid default auth.uid()
)
returns boolean language sql stable security definer set search_path = '' as $$
  select
    (target_team_id is not null and private.is_team_manager(target_team_id, target_user_id))
    or (target_department_id is not null and private.is_department_admin(target_department_id, target_user_id))
    or (target_organization_id is not null and private.is_organization_admin(target_organization_id, target_user_id));
$$;

create or replace function private.quality_scope_is_consistent(
  target_organization_id uuid,
  target_department_id uuid,
  target_team_id uuid
)
returns boolean language sql stable security definer set search_path = '' as $$
  select case
    when target_team_id is not null then exists (
      select 1 from public.teams t
      where t.id = target_team_id
        and (target_organization_id is null or t.organization_id = target_organization_id)
        and (target_department_id is null or t.department_id = target_department_id)
    )
    when target_department_id is not null then exists (
      select 1 from public.departments d
      where d.id = target_department_id
        and d.organization_id = target_organization_id
    )
    else target_organization_id is not null
  end;
$$;

create or replace function private.validate_quality_scope()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if not private.quality_scope_is_consistent(new.organization_id, new.department_id, new.team_id) then
    raise exception 'quality scope does not match the selected team or department'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger meeting_templates_validate_scope before insert or update
on public.meeting_templates for each row execute function private.validate_quality_scope();
create trigger glossary_terms_validate_scope before insert or update
on public.glossary_terms for each row execute function private.validate_quality_scope();

create or replace function private.validate_meeting_template_scope()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if new.template_id is not null and not exists (
    select 1
    from public.teams t
    join public.meeting_templates mt on mt.id = new.template_id and mt.is_active
    where t.id = new.team_id
      and (
        mt.team_id = t.id
        or (
          mt.team_id is null
          and mt.organization_id = t.organization_id
          and (mt.department_id is null or mt.department_id = t.department_id)
        )
      )
  ) then
    raise exception 'template is not available to the meeting team'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger meetings_validate_template_scope
before insert or update of template_id, team_id on public.meetings
for each row execute function private.validate_meeting_template_scope();

create or replace function public.set_meeting_attendees(
  target_meeting_id uuid,
  attendee_items jsonb
)
returns void language plpgsql security invoker set search_path = '' as $$
declare
  item jsonb;
  meeting_team_id uuid;
begin
  if not private.can_manage_meeting(target_meeting_id) then
    raise exception 'meeting access denied' using errcode = '42501';
  end if;
  if jsonb_typeof(attendee_items) <> 'array' or jsonb_array_length(attendee_items) > 100 then
    raise exception 'invalid attendee list' using errcode = '22023';
  end if;
  select team_id into meeting_team_id from public.meetings
  where id = target_meeting_id and deleted_at is null;
  if meeting_team_id is null then
    raise exception 'meeting not found' using errcode = 'P0002';
  end if;

  delete from public.meeting_attendees where meeting_id = target_meeting_id;
  for item in select value from jsonb_array_elements(attendee_items)
  loop
    if item->>'user_id' is not null
       and not private.is_active_team_member(meeting_team_id, (item->>'user_id')::uuid) then
      raise exception 'attendee is not an active team member' using errcode = '42501';
    end if;
    insert into public.meeting_attendees(
      meeting_id, user_id, external_name, external_organization
    ) values (
      target_meeting_id,
      nullif(item->>'user_id', '')::uuid,
      nullif(btrim(item->>'external_name'), ''),
      nullif(btrim(item->>'external_organization'), '')
    );
  end loop;
end;
$$;

create or replace function public.save_transcript_correction(
  target_meeting_id uuid,
  target_transcript_id uuid,
  corrected_value text,
  correction_changes jsonb,
  correction_uncertainties jsonb,
  context_value jsonb,
  provider_value text,
  model_value text
)
returns uuid language plpgsql security invoker set search_path = '' as $$
declare
  correction_id uuid := gen_random_uuid();
  source_text text;
  item jsonb;
begin
  if not private.can_manage_meeting(target_meeting_id) then
    raise exception 'meeting access denied' using errcode = '42501';
  end if;
  select original_text into source_text from public.meeting_transcripts
  where id = target_transcript_id and meeting_id = target_meeting_id;
  if source_text is null then
    raise exception 'transcript not found' using errcode = 'P0002';
  end if;
  if jsonb_typeof(correction_changes) <> 'array'
     or jsonb_typeof(correction_uncertainties) <> 'array'
     or jsonb_typeof(context_value) <> 'object' then
    raise exception 'invalid correction payload' using errcode = '22023';
  end if;

  insert into public.transcript_corrections(
    id, transcript_id, meeting_id, original_text, corrected_text, changes,
    uncertainties, context_snapshot, provider, model, created_by
  ) values (
    correction_id, target_transcript_id, target_meeting_id, source_text,
    corrected_value, correction_changes, correction_uncertainties,
    context_value, provider_value, model_value, auth.uid()
  );
  update public.meeting_transcripts set corrected_text = corrected_value
  where id = target_transcript_id;

  for item in select value from jsonb_array_elements(correction_uncertainties)
  loop
    insert into public.meeting_questions(
      meeting_id, category, question, evidence, created_by
    ) values (
      target_meeting_id,
      item->>'category',
      item->>'question',
      nullif(item->>'evidence', ''),
      auth.uid()
    );
  end loop;
  return correction_id;
end;
$$;

create or replace function public.apply_transcript_speaker_edit(
  target_meeting_id uuid,
  target_segment_id uuid,
  target_speaker_id uuid,
  edit_scope text
)
returns uuid language plpgsql security invoker set search_path = '' as $$
declare
  batch_id uuid := gen_random_uuid();
  transcript_value uuid;
  start_index integer;
  original_speaker uuid;
  change_items jsonb;
begin
  if not private.can_manage_meeting(target_meeting_id) then
    raise exception 'meeting access denied' using errcode = '42501';
  end if;
  if edit_scope not in ('single', 'following') then
    raise exception 'invalid speaker edit scope' using errcode = '22023';
  end if;
  select transcript_id, segment_index, speaker_id
    into transcript_value, start_index, original_speaker
  from public.transcript_segments
  where id = target_segment_id and meeting_id = target_meeting_id;
  if transcript_value is null or not exists (
    select 1 from public.transcript_speakers
    where id = target_speaker_id and transcript_id = transcript_value
  ) then
    raise exception 'segment or speaker not found' using errcode = 'P0002';
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'segment_id', s.id,
    'previous_speaker_id', coalesce(e.speaker_id, s.speaker_id)
  ) order by s.segment_index), '[]'::jsonb)
  into change_items
  from public.transcript_segments s
  left join public.transcript_segment_speaker_edits e on e.segment_id = s.id
  where s.transcript_id = transcript_value
    and (
      s.id = target_segment_id
      or (edit_scope = 'following' and s.segment_index >= start_index and s.speaker_id = original_speaker)
    );

  insert into public.transcript_speaker_edit_batches(
    id, meeting_id, transcript_id, changes, created_by
  ) values (batch_id, target_meeting_id, transcript_value, change_items, auth.uid());

  insert into public.transcript_segment_speaker_edits(
    segment_id, meeting_id, transcript_id, speaker_id, batch_id, updated_by
  )
  select s.id, target_meeting_id, transcript_value, target_speaker_id, batch_id, auth.uid()
  from public.transcript_segments s
  where s.transcript_id = transcript_value
    and (
      s.id = target_segment_id
      or (edit_scope = 'following' and s.segment_index >= start_index and s.speaker_id = original_speaker)
    )
  on conflict (segment_id) do update set
    speaker_id = excluded.speaker_id,
    batch_id = excluded.batch_id,
    updated_by = excluded.updated_by,
    updated_at = now();
  return batch_id;
end;
$$;

create or replace function public.undo_transcript_speaker_edit(target_batch_id uuid)
returns integer language plpgsql security invoker set search_path = '' as $$
declare
  batch_row public.transcript_speaker_edit_batches%rowtype;
  item jsonb;
  changed integer := 0;
  original_speaker uuid;
begin
  select * into batch_row from public.transcript_speaker_edit_batches
  where id = target_batch_id and reverted_at is null;
  if batch_row.id is null then
    raise exception 'speaker edit not found' using errcode = 'P0002';
  end if;
  if not private.can_manage_meeting(batch_row.meeting_id) then
    raise exception 'meeting access denied' using errcode = '42501';
  end if;
  for item in select value from jsonb_array_elements(batch_row.changes)
  loop
    select speaker_id into original_speaker from public.transcript_segments
    where id = (item->>'segment_id')::uuid;
    if (item->>'previous_speaker_id')::uuid = original_speaker then
      delete from public.transcript_segment_speaker_edits
      where segment_id = (item->>'segment_id')::uuid;
    else
      update public.transcript_segment_speaker_edits
      set speaker_id = (item->>'previous_speaker_id')::uuid,
          updated_by = auth.uid(), updated_at = now()
      where segment_id = (item->>'segment_id')::uuid;
    end if;
    changed := changed + 1;
  end loop;
  update public.transcript_speaker_edit_batches set reverted_at = now()
  where id = target_batch_id;
  return changed;
end;
$$;

alter table public.meeting_templates enable row level security;
alter table public.meeting_template_versions enable row level security;
alter table public.glossary_terms enable row level security;
alter table public.meeting_attendees enable row level security;
alter table public.transcript_corrections enable row level security;
alter table public.meeting_questions enable row level security;
alter table public.transcript_speaker_edit_batches enable row level security;
alter table public.transcript_segment_speaker_edits enable row level security;

create policy meeting_templates_select_scope on public.meeting_templates for select to authenticated
using (private.can_view_quality_scope(organization_id, department_id, team_id));
create policy meeting_templates_insert_manager on public.meeting_templates for insert to authenticated
with check (created_by = auth.uid() and private.can_manage_quality_scope(organization_id, department_id, team_id));
create policy meeting_templates_update_manager on public.meeting_templates for update to authenticated
using (private.can_manage_quality_scope(organization_id, department_id, team_id))
with check (private.can_manage_quality_scope(organization_id, department_id, team_id));
create policy meeting_templates_delete_manager on public.meeting_templates for delete to authenticated
using (private.can_manage_quality_scope(organization_id, department_id, team_id));
create policy meeting_template_versions_select_scope on public.meeting_template_versions
for select to authenticated using (
  exists (
    select 1 from public.meeting_templates mt
    where mt.id = template_id
      and private.can_view_quality_scope(mt.organization_id, mt.department_id, mt.team_id)
  )
);

create policy glossary_terms_select_scope on public.glossary_terms for select to authenticated
using (private.can_view_quality_scope(organization_id, department_id, team_id));
create policy glossary_terms_insert_manager on public.glossary_terms for insert to authenticated
with check (created_by = auth.uid() and private.can_manage_quality_scope(organization_id, department_id, team_id));
create policy glossary_terms_update_manager on public.glossary_terms for update to authenticated
using (private.can_manage_quality_scope(organization_id, department_id, team_id))
with check (private.can_manage_quality_scope(organization_id, department_id, team_id));
create policy glossary_terms_delete_manager on public.glossary_terms for delete to authenticated
using (private.can_manage_quality_scope(organization_id, department_id, team_id));

create policy meeting_attendees_select_viewer on public.meeting_attendees for select to authenticated
using (private.can_view_meeting(meeting_id));
create policy meeting_attendees_write_manager on public.meeting_attendees for all to authenticated
using (private.can_manage_meeting(meeting_id))
with check (
  private.can_manage_meeting(meeting_id)
  and (
    user_id is null
    or exists (
      select 1 from public.meetings m
      where m.id = meeting_id and private.is_active_team_member(m.team_id, user_id)
    )
  )
);

create policy transcript_corrections_select_viewer on public.transcript_corrections for select to authenticated
using (private.can_view_meeting(meeting_id));
create policy transcript_corrections_insert_manager on public.transcript_corrections for insert to authenticated
with check (created_by = auth.uid() and private.can_manage_meeting(meeting_id));

create policy meeting_questions_select_viewer on public.meeting_questions for select to authenticated
using (private.can_view_meeting(meeting_id));
create policy meeting_questions_insert_manager on public.meeting_questions for insert to authenticated
with check (created_by = auth.uid() and private.can_manage_meeting(meeting_id));
create policy meeting_questions_update_manager on public.meeting_questions for update to authenticated
using (private.can_manage_meeting(meeting_id))
with check (private.can_manage_meeting(meeting_id));
create policy meeting_questions_delete_manager on public.meeting_questions for delete to authenticated
using (private.can_manage_meeting(meeting_id));

create policy transcript_speaker_edit_batches_select_viewer on public.transcript_speaker_edit_batches for select to authenticated
using (private.can_view_meeting(meeting_id));
create policy transcript_speaker_edit_batches_insert_manager on public.transcript_speaker_edit_batches for insert to authenticated
with check (created_by = auth.uid() and private.can_manage_meeting(meeting_id));
create policy transcript_speaker_edit_batches_update_manager on public.transcript_speaker_edit_batches for update to authenticated
using (private.can_manage_meeting(meeting_id))
with check (private.can_manage_meeting(meeting_id));
create policy transcript_segment_speaker_edits_select_viewer on public.transcript_segment_speaker_edits for select to authenticated
using (private.can_view_meeting(meeting_id));
create policy transcript_segment_speaker_edits_write_manager on public.transcript_segment_speaker_edits for all to authenticated
using (private.can_manage_meeting(meeting_id))
with check (private.can_manage_meeting(meeting_id));

revoke all on public.meeting_templates, public.glossary_terms, public.meeting_attendees,
  public.transcript_corrections, public.meeting_questions,
  public.transcript_speaker_edit_batches, public.transcript_segment_speaker_edits
from anon, authenticated;
revoke all on public.meeting_template_versions from anon, authenticated;
grant select, insert, update, delete on public.meeting_templates, public.glossary_terms,
  public.meeting_attendees, public.meeting_questions,
  public.transcript_speaker_edit_batches, public.transcript_segment_speaker_edits to authenticated;
grant select, insert on public.transcript_corrections to authenticated;
grant select on public.meeting_template_versions to authenticated;
grant update(topic, location, meeting_type, purpose, project_name, template_id, metadata_confirmed_at)
  on public.meetings to authenticated;
grant update(corrected_text) on public.meeting_transcripts to authenticated;

revoke all on function public.set_meeting_attendees(uuid, jsonb) from public;
revoke all on function public.save_transcript_correction(uuid, uuid, text, jsonb, jsonb, jsonb, text, text) from public;
revoke all on function public.apply_transcript_speaker_edit(uuid, uuid, uuid, text) from public;
revoke all on function public.undo_transcript_speaker_edit(uuid) from public;
grant execute on function public.set_meeting_attendees(uuid, jsonb) to authenticated;
grant execute on function public.save_transcript_correction(uuid, uuid, text, jsonb, jsonb, jsonb, text, text) to authenticated;
grant execute on function public.apply_transcript_speaker_edit(uuid, uuid, uuid, text) to authenticated;
grant execute on function public.undo_transcript_speaker_edit(uuid) to authenticated;

grant select, insert on public.transcript_corrections, public.meeting_questions to service_role;

revoke all on function private.can_view_quality_scope(uuid, uuid, uuid, uuid) from public;
revoke all on function private.can_manage_quality_scope(uuid, uuid, uuid, uuid) from public;
revoke all on function private.quality_scope_is_consistent(uuid, uuid, uuid) from public;
revoke all on function private.validate_quality_scope() from public;
revoke all on function private.validate_meeting_template_scope() from public;
revoke all on function private.capture_meeting_template_version() from public;
grant execute on function private.can_view_quality_scope(uuid, uuid, uuid, uuid) to authenticated;
grant execute on function private.can_manage_quality_scope(uuid, uuid, uuid, uuid) to authenticated;

commit;
