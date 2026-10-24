-- CoachBadge newsletter signup. Separate coachbadge_ tables in the shared project (which also hosts sbi_ and fut_ tables).
-- Stored per subscriber: email and signup time. Nothing else (no IP, no user agent).
-- The public (anon/publishable) key may only INSERT; it cannot read, update or delete anything.

create table if not exists public.coachbadge_subscribers (
  id bigint generated always as identity primary key,
  email text not null,
  created_at timestamptz not null default now(),
  cb_hp_note text,  -- honeypot; always null in stored rows (the trigger drops any insert that fills it)
  constraint coachbadge_subscribers_email_len check (char_length(email) between 6 and 254),
  constraint coachbadge_subscribers_email_fmt check (email ~ '^[^[:space:]@<>(),;:"]{1,64}@[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$'),
  constraint coachbadge_subscribers_hp_null check (cb_hp_note is null)
);
create unique index if not exists coachbadge_subscribers_email_key on public.coachbadge_subscribers (lower(email));

-- Removal requests: insert-only too. The trigger deletes the matching subscriber and stores nothing.
create table if not exists public.coachbadge_unsubscribes (
  email text not null,
  cb_hp_note text
);

alter table public.coachbadge_subscribers enable row level security;
alter table public.coachbadge_unsubscribes enable row level security;
revoke all on public.coachbadge_subscribers from anon, authenticated;
revoke all on public.coachbadge_unsubscribes from anon, authenticated;
grant insert (email, cb_hp_note) on public.coachbadge_subscribers to anon;
grant insert (email, cb_hp_note) on public.coachbadge_unsubscribes to anon;

drop policy if exists coachbadge_subscribers_anon_insert on public.coachbadge_subscribers;
create policy coachbadge_subscribers_anon_insert on public.coachbadge_subscribers
  for insert to anon with check (char_length(email) <= 254 and position('@' in email) > 1);
drop policy if exists coachbadge_unsubscribes_anon_insert on public.coachbadge_unsubscribes;
create policy coachbadge_unsubscribes_anon_insert on public.coachbadge_unsubscribes
  for insert to anon with check (char_length(email) <= 254);
-- No select/update/delete policies: only service_role (dashboard, MCP) can read or remove rows.

-- Before insert: honeypot filled -> silently drop (the client still sees success); normalise the email;
-- already subscribed -> silently skip, so the response never reveals whether an address is on the list.
create or replace function public.coachbadge_subscribers_before_insert()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if coalesce(btrim(new.cb_hp_note), '') <> '' then return null; end if;
  new.cb_hp_note := null;
  new.email := lower(btrim(new.email));
  new.created_at := now();
  if exists (select 1 from public.coachbadge_subscribers s where lower(s.email) = new.email) then return null; end if;
  return new;
end $$;
drop trigger if exists coachbadge_subscribers_bi on public.coachbadge_subscribers;
create trigger coachbadge_subscribers_bi before insert on public.coachbadge_subscribers
  for each row execute function public.coachbadge_subscribers_before_insert();

create or replace function public.coachbadge_unsubscribes_before_insert()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if coalesce(btrim(new.cb_hp_note), '') = '' then
    delete from public.coachbadge_subscribers where lower(email) = lower(btrim(new.email));
  end if;
  return null;  -- never store the request itself
end $$;
drop trigger if exists coachbadge_unsubscribes_bi on public.coachbadge_unsubscribes;
create trigger coachbadge_unsubscribes_bi before insert on public.coachbadge_unsubscribes
  for each row execute function public.coachbadge_unsubscribes_before_insert();

revoke all on function public.coachbadge_subscribers_before_insert() from public, anon, authenticated;
revoke all on function public.coachbadge_unsubscribes_before_insert() from public, anon, authenticated;
