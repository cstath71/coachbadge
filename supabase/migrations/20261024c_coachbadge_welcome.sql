-- CoachBadge welcome email switch (24 Oct 2026): the switch lives in Supabase Vault (secret coachbadge_welcome_enabled = 'true'),
-- so it can be flipped without redeploying. The function's WELCOME_ENABLED secret, when set to "true" or "false", still overrides it.
do $$
begin
  if exists (select 1 from vault.secrets where name = 'coachbadge_welcome_enabled') then
    perform vault.update_secret((select id from vault.secrets where name = 'coachbadge_welcome_enabled'), 'true');
  else
    perform vault.create_secret('true', 'coachbadge_welcome_enabled', 'CoachBadge welcome email switch (true/false)');
  end if;
end $$;

-- Mail settings for the coachbadge-subscribe function: Resend API key and the welcome switch, both from Vault.
-- The return type changes, so the function is dropped and recreated. Callable by service_role only.
drop function if exists public.coachbadge_mail_config();
create function public.coachbadge_mail_config()
returns table (api_key text, welcome_enabled boolean) language sql security definer set search_path = '' stable as $$
  select (select decrypted_secret from vault.decrypted_secrets where name = 'coachbadge_resend_api_key' limit 1),
         coalesce((select decrypted_secret from vault.decrypted_secrets where name = 'coachbadge_welcome_enabled' limit 1) = 'true', false);
$$;
revoke all on function public.coachbadge_mail_config() from public, anon, authenticated;
grant execute on function public.coachbadge_mail_config() to service_role;
