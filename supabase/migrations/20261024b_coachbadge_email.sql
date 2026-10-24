-- CoachBadge emails (24 Oct 2026): sign-ups now go through the coachbadge-subscribe Edge Function, which sends a welcome
-- email through Resend (from hello@coachbadge.com). Every subscriber gets a random unsubscribe token; the old open removal form is switched off.

-- Per-subscriber unsubscribe token and the time the welcome email went out.
alter table public.coachbadge_subscribers add column if not exists token uuid not null default gen_random_uuid();
create unique index if not exists coachbadge_subscribers_token_key on public.coachbadge_subscribers (token);
alter table public.coachbadge_subscribers add column if not exists welcomed_at timestamptz;

-- Rate limit: hashed (IP + clock hour) per sign-up attempt; the function deletes rows older than two hours.
create table if not exists public.coachbadge_signup_attempts (
  id bigint generated always as identity primary key,
  ip_hash text not null,
  created_at timestamptz not null default now()
);
create index if not exists coachbadge_signup_attempts_hash_idx on public.coachbadge_signup_attempts (ip_hash, created_at);
alter table public.coachbadge_signup_attempts enable row level security;
revoke all on public.coachbadge_signup_attempts from anon, authenticated;

-- The public key can no longer write directly: the site forms post to the function (rate limit, welcome email).
revoke insert on public.coachbadge_subscribers from anon;
drop policy if exists coachbadge_subscribers_anon_insert on public.coachbadge_subscribers;
-- The open "Remove my email" form let anyone delete any address. Switched off; removal is by token only.
revoke insert on public.coachbadge_unsubscribes from anon;
drop policy if exists coachbadge_unsubscribes_anon_insert on public.coachbadge_unsubscribes;

-- One-click unsubscribe by token: deletes the row (address, sign-up time, token) and keeps no record of the request.
create or replace function public.coachbadge_unsubscribe(p_token uuid)
returns boolean language plpgsql security definer set search_path = '' as $$
declare n int;
begin
  delete from public.coachbadge_subscribers where token = p_token;
  get diagnostics n = row_count;
  return n > 0;
end $$;
revoke all on function public.coachbadge_unsubscribe(uuid) from public, anon, authenticated;
grant execute on function public.coachbadge_unsubscribe(uuid) to service_role;

-- Mail provider (Resend) API key from Supabase Vault (secret name coachbadge_resend_api_key), for when it is not set as a
-- function secret (MAIL_API_KEY / RESEND_API_KEY). Callable by service_role only.
create or replace function public.coachbadge_mail_config()
returns table (api_key text) language sql security definer set search_path = '' stable as $$
  select (select decrypted_secret from vault.decrypted_secrets where name = 'coachbadge_resend_api_key' limit 1);
$$;
revoke all on function public.coachbadge_mail_config() from public, anon, authenticated;
grant execute on function public.coachbadge_mail_config() to service_role;
