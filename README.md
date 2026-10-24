# CoachBadge

**Every open coaching course in Europe, football and basketball, with deadlines and prices.**

Live: https://cstath71.github.io/coachbadge/

CoachBadge is a static board of coaching courses (UEFA C, B, A, Pro, Elite Youth; national basketball federations and FIBA Europe).
Each entry carries provider, country, level, deadline or application window, start date, price, language, format, status,
a source link, the date it was last checked, and the verbatim sentences from the source page that support it.

Independent; not affiliated with UEFA, FIBA or any association listed.

## Layout

| Path | What |
|---|---|
| `config/site.json` | Brand, domain, wordmark, tagline, base URL, disclaimer. A rename is a one-line change here. |
| `data/sources.yaml` | Every source page, whether it was readable, and why not. |
| `data/manual_courses.yaml` | Hand-verified courses with evidence quotes. |
| `data/courses.json` | Generated course list (`scripts/extract.py`). |
| `scripts/fetch.py` | Polite fetcher: robots.txt, `CoachBadgeBot` user agent, 3 s per host, local cache in `raw/`. |
| `scripts/extract.py` | Parsers for pages with course tables, plus the manual file. |
| `scripts/refresh.py` | Weekly, restartable re-check. Writes `reports/refresh-DATE.md` with diffs. Never publishes. |
| `scripts/build.py` | Builds the site into `dist/`. |
| `tests/` | Data validation, banned words, wordmark position, link checks. |

## Weekly routine

```
python3 scripts/refresh.py          # resumable; re-run if interrupted
# read reports/refresh-DATE.md, update data/manual_courses.yaml where needed
python3 scripts/extract.py
python3 scripts/build.py && python3 -m unittest discover -s tests -v
git commit -am "Weekly refresh" && git push   # GitHub Pages deploys on push
```

Rules: only data that appears on the provider's own page; no invented dates, prices or statuses; "open" only when the page says so.

## Licence

© CoachBadge. All rights reserved. Linking and short quotes with credit and a link are welcome.
