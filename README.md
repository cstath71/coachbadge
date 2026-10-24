# CoachBadge

**Every open football coaching course in Europe, with deadlines and prices.**

Live: https://coachbadge.com/ (until the custom domain is switched on: https://cstath71.github.io/coachbadge/)

CoachBadge is a static board of football coaching courses (UEFA C, B, A, Pro, Elite Youth and goalkeeper courses).
Each entry carries provider, country, level, deadline or application window, start date, price, language, format, status,
a source link, the date it was last checked, and the verbatim sentences from the source page that support it.

Independent; not affiliated with UEFA or any association listed.

## Layout

| Path | What |
|---|---|
| `config/site.json` | Brand, domain, wordmark, tagline, base URL, disclaimer. A rename is a one-line change here. |
| `data/sources.yaml` | Every source page, whether it was readable, and why not. |
| `data/manual_courses.yaml` | Hand-verified courses with evidence quotes. |
| `data/courses.json` | Generated course list (`scripts/extract.py`). |
| `scripts/fetch.py` | Polite fetcher: robots.txt, `CoachBadgeBot` user agent, 3 s per host, local cache in `raw/`. |
| `scripts/render.py` | Same rules as `fetch.py`, but renders JavaScript-only pages in headless Chrome. Gives up on a 403, a bot check or a login; never clicks through. |
| `scripts/extract.py` | Parsers for pages with course tables, plus the manual file. |
| `scripts/refresh.py` | Weekly, restartable re-check. Writes `reports/refresh-DATE.md` with diffs. Never publishes. |
| `scripts/build.py` | Builds the site into `dist/`. |
| `tests/` | Data validation, banned words, wordmark position, link checks. |

## JavaScript-only pages

Some association pages (e.g. the Carinthian and Tyrolean FA course lists) build their text with JavaScript. Mark such a course in
`data/manual_courses.yaml` (or a source in `data/sources.yaml`) with `render: true`; the evidence test and `scripts/refresh.py` then read
that page through `scripts/render.py`. A page that needs a login or shows a bot check stays `readable: "no"`.

## Countries without courses

A country or level with no open course shows "No open courses right now", the reason from its `sources.yaml` entries in plain words and
links to the association's course pages. Listings show "Check association" instead of a zero count.

## Switched-off sources

A source in `data/sources.yaml` with `enabled: false` stays in the file but is skipped everywhere: `scripts/refresh.py` does not fetch it,
`scripts/extract.py` leaves out courses of any sport that has no enabled source, and `scripts/build.py` shows neither its courses nor its pages.
The site is football-only for now; the other sport's sources are kept there, switched off, so they can come back later by removing the flag.
The shared loader is `scripts/sources.py`.

## Weekly routine

```
python3 scripts/refresh.py          # resumable; re-run if interrupted
# read reports/refresh-DATE.md, update data/manual_courses.yaml where needed
python3 scripts/extract.py
python3 scripts/build.py && python3 -m unittest discover -s tests -v
git commit -am "Weekly refresh" && git push   # GitHub Pages deploys on push
```

Rules: only data that appears on the provider's own page; no invented dates, prices or statuses; "open" only when the page says so.

## Newsletter

- Forms: near the top of the home page (`#subscribe-top`), on `newsletter.html`, plus a dismissible bar fixed to the bottom of other pages. Promise: one free short email a week with newly opened courses and deadlines coming up, and an unsubscribe link in every email.
- Sign-up: the forms post `{email, cb_hp_note}` to the Supabase Edge Function `coachbadge-subscribe` (`supabase/functions/coachbadge-subscribe/`, deploy with `verify_jwt = false`). It drops honeypot hits, validates the address, rate-limits to 5 attempts per IP per hour (only a hash of IP + hour is kept, for two hours), and inserts with the service role. No key of any kind is in the site.
- Storage: table `public.coachbadge_subscribers` in the shared Supabase project (EU region): email, `created_at`, a random `token` (unsubscribe) and `welcomed_at`. RLS on; since `20261024b_coachbadge_email.sql` the public key cannot write at all. A before-insert trigger lower-cases the email and silently skips duplicates (the response never reveals whether an address is on the list).
- Unsubscribe: every email links to `unsubscribe.html?t=TOKEN` (noindex, not in the sitemap), which posts the token once on load, and carries `List-Unsubscribe` + `List-Unsubscribe-Post: List-Unsubscribe=One-Click` pointing at the function (`?unsubscribe=TOKEN`). The row is deleted and nothing is kept. The old open "Remove my email" form is gone (`coachbadge_unsubscribes` is left in place, unused).
- Welcome email: `supabase/functions/coachbadge-subscribe/email.mjs` (shared by the function and the tests). Sent only when the function setting `WELCOME_ENABLED=true`; it is off. `config/site.json` `email.welcome_enabled` switches the site copy to match.
- Weekly email: `scripts/send_newsletter.py` builds the issue only from `data/courses.json` and the latest `reports/refresh-*.md` (newly opened, updated open courses, deadlines in the next 30 days; every item links to the provider's page). Templates: `templates/newsletter.html` and `.txt`.
  - `python3 scripts/send_newsletter.py` dry run: writes `out/newsletter-DATE.html/.txt/.json`, sends nothing.
  - `--to ADDRESS` one test copy (subject starts with `[Test]`).
  - `--send-to-subscribers --confirm DATE` everyone; only when run by hand. Nothing schedules it. Refuses an empty issue unless `--allow-empty`.
- Sender and provider are settings, not code:
  - site and script: `config/site.json` `email` (`provider`, `from_address`, `from_name`, `reply_to`, `api_base`, `welcome_enabled`); env overrides `MAIL_PROVIDER`, `MAIL_FROM`, `MAIL_REPLY_TO`, `MAIL_API_BASE`; key in `MAIL_API_KEY` (or `RESEND_API_KEY`), never in the repo.
  - function: secrets `WELCOME_ENABLED`, `MAIL_PROVIDER`, `MAIL_FROM`, `MAIL_REPLY_TO`, `MAIL_API_BASE`, `MAIL_API_KEY` (or `RESEND_API_KEY`, or Vault secret `coachbadge_resend_api_key`), `SITE_URL`, `PUBLIC_FUNCTION_URL`.
  - Provider: Resend (`MAIL_PROVIDER=resend`), from `CoachBadge <hello@coachbadge.com>`, reply-to hello@coachbadge.com; List-Unsubscribe / List-Unsubscribe-Post go as custom headers. Needs coachbadge.com verified in Resend (DNS on the `send` subdomain + `resend._domainkey`, so Zoho's SPF on `@` is untouched). AgentMail (`MAIL_PROVIDER=agentmail`, earlier test inbox coachbadge@agentmail.to) is kept only as a fallback.
- Tests: `tests/test_signup.py`, `tests/test_email.py`.

## Search and answer engines

`scripts/build.py` (helpers in `scripts/seo.py`) writes, on every build:

- `robots.txt`: allows every crawler, including AI search and assistant bots (GPTBot, OAI-SearchBot, ClaudeBot, PerplexityBot, Google-Extended and others), plus the Sitemap line.
- `sitemap.xml`: every indexable page with a real `lastmod` (data date; country and level pages use the latest check of their sources). `unsubscribe.html` and `404.html` are noindex and left out.
- `llms.txt` and `llms-full.txt`: plain-text summary for language models; every number is computed from `data/courses.json`.
- JSON-LD: WebSite + Organization on the home page, BreadcrumbList on subpages, ItemList of Course items on the home, country and level pages (Course fields, CourseInstance dates/location and Offer price only when the provider page gave them), FAQPage matching the visible FAQ.
- Answer-first summary (`#summary`) under the h1 on the home, country and level pages; unique title/description, absolute canonical, Open Graph and Twitter tags (`og.png`; brand SVGs in `site/brand/` from `scripts/brand.py`, PNGs and favicon.ico from `scripts/make_images.py`).
- IndexNow key file at the site root. After a deploy is live, run `python3 scripts/indexnow.py` (`--dry` to preview) to submit all sitemap URLs.
- Search Console / Bing: put a verification token in `config/site.json` (`google_site_verification`, `msvalidate`) and it renders as a meta tag; empty means no tag.

`tests/test_seo.py` checks all of the above.

## Licence

© CoachBadge. All rights reserved. Linking and short quotes with credit and a link are welcome.
