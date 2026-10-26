-- CoachBadge: cookie-free page-view counter (26 Oct 2026). Separate coachbadge_ table in the shared project (sbi_, fut_ also live here).
-- Only daily totals are stored: day (Zurich time), page path, referrer domain, utm_ tags and a count.
-- No IP address, no user agent, no cookies, no identifiers.
create table if not exists public.coachbadge_page_views (
  day date not null,
  path text not null,
  ref_domain text not null default '',
  utm_source text not null default '',
  utm_medium text not null default '',
  utm_campaign text not null default '',
  views integer not null default 0,
  primary key (day, path, ref_domain, utm_source, utm_medium, utm_campaign)
);
alter table public.coachbadge_page_views enable row level security;  -- no policies: only service_role can read or write
revoke all on public.coachbadge_page_views from anon, authenticated;

create or replace function public.coachbadge_count_view(p_path text, p_ref text, p_us text, p_um text, p_uc text)
returns void language sql security definer set search_path = '' as $$
  insert into public.coachbadge_page_views as v (day, path, ref_domain, utm_source, utm_medium, utm_campaign, views)
  values ((now() at time zone 'Europe/Zurich')::date, left(p_path,200), left(coalesce(p_ref,''),100), left(coalesce(p_us,''),64), left(coalesce(p_um,''),64), left(coalesce(p_uc,''),64), 1)
  on conflict (day, path, ref_domain, utm_source, utm_medium, utm_campaign) do update set views = v.views + 1;
$$;
revoke all on function public.coachbadge_count_view(text,text,text,text,text) from public, anon, authenticated;
grant execute on function public.coachbadge_count_view(text,text,text,text,text) to service_role;
