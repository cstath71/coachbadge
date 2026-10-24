"""Build the static site into dist/. Usage: python3 scripts/build.py [--today YYYY-MM-DD]"""
import datetime, html, json, os, re, shutil, sys, unicodedata
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
CFG = json.load(open(os.path.join(ROOT, "config", "site.json")))
DATA = json.load(open(os.path.join(ROOT, "data", "courses.json")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import enabled as enabled_sources
SOURCES = enabled_sources()  # sources with enabled: false (basketball, for now) are left out of the site
TODAY = datetime.date.fromisoformat(sys.argv[sys.argv.index("--today") + 1]) if "--today" in sys.argv else datetime.date.today()
CLOSING_DAYS = 30
BASE = CFG["base_url"].rstrip("/") + "/"
BRAND = CFG["brand"]
e = lambda s: html.escape(str(s if s is not None else ""), quote=True)

STATUS_LABEL = {"open": "Open", "closing_soon": "Closing soon", "full": "Full / waitlist", "closed": "Closed",
                "upcoming": "Upcoming", "unknown": "Check provider"}
FORMAT_LABEL = {"residential": "In person", "online": "Online", "blended": "Blended", None: "Not stated"}
CUR = {"GBP": "£", "EUR": "€"}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

def pdate(s):
    if not s: return None
    try: return datetime.date.fromisoformat(s[:10]) if len(s) >= 10 else None
    except ValueError: return None

def fdate(s):
    if not s: return ""
    p = s.split("-")
    if len(p) == 3: return f"{int(p[2])} {MONTHS[int(p[1]) - 1]} {p[0]}"
    if len(p) == 2: return f"{MONTHS[int(p[1]) - 1]} {p[0]}"
    return s

def fprice(p):
    if not p or p.get("amount") is None: return ""
    a = p["amount"]; a = int(a) if float(a).is_integer() else a
    sym = CUR.get(p["currency"])
    return f"{sym}{a:,}" if sym else f"{a:,} {p['currency']}"

def price_text(c):
    p = c.get("price"); base = fprice(p)
    note = (p or {}).get("note") or c.get("price_note")
    if base: return base + (f" ({note})" if note else "")
    return ("Not listed" + (f" – {note}" if note else ""))

def status(c):
    s = c["status"]
    if s == "open":
        d = pdate(c.get("deadline"))
        if d and d < TODAY: return "closed"
        if d and (d - TODAY).days <= CLOSING_DAYS: return "closing_soon"
    return s

COURSES = []
for c in DATA["courses"]:
    if c["sport"] not in SOURCES: continue  # belt and braces: no course from a switched-off sport
    c = dict(c); c["display_status"] = status(c); COURSES.append(c)
ORDER = {"closing_soon": 0, "open": 1, "full": 2, "upcoming": 3, "unknown": 4, "closed": 5}
def sortkey(c): return (ORDER[c["display_status"]], c.get("deadline") or "9999", c.get("start_date") or "9999", c["id"])
COURSES.sort(key=sortkey)
LIVE = [c for c in COURSES if c["display_status"] in ("open", "closing_soon")]

ALL_SOURCES = [dict(s, sport=sp) for sp, lst in SOURCES.items() for s in lst]
COUNTRIES = sorted({c["country"] for c in COURSES} | {s["country"] for s in ALL_SOURCES})
LEVELS = sorted({c["level"] for c in COURSES})
SPORTS = sorted({c["sport"] for c in COURSES})

BADGE = ('<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M20 2 35 8v11c0 9-6.5 16-15 19C11.5 35 5 28 5 19V8z" '
         'fill="#c6f432"/><path d="M20 6 31 10.5v8.5c0 7-4.8 12.6-11 15-6.2-2.4-11-8-11-15v-8.5z" fill="#0b1f33"/>'
         '<path d="m13.5 20 4.5 4.5 8.5-9" stroke="#c6f432" stroke-width="3.2" fill="none" stroke-linecap="round" '
         'stroke-linejoin="round"/></svg>')

def counter_js():
    ep = json.dumps(CFG.get("counter_endpoint", ""))
    host = json.dumps(BASE.split("/")[2])
    return ("<script>/* page counter: inert unless an endpoint is configured; no cookies, no storage, no ids */"
            f"(function(){{var E={ep};if(!E)return;var n=navigator;if(n.webdriver)return;"
            "if(n.doNotTrack=='1'||window.doNotTrack=='1'||n.globalPrivacyControl)return;"
            f"if(location.hostname!=={host})return;if(/bot|crawl|spider|headless/i.test(n.userAgent))return;"
            "if(n.sendBeacon)n.sendBeacon(E,location.pathname);})();</script>")

# ---- newsletter (24 Oct 2026): the forms post to the coachbadge-subscribe Edge Function (honeypot, de-duplication,
# rate limit, welcome email via AgentMail). No key of any kind is in the site. Removal is by the per-subscriber token link only.
NL_PROMISE = "One free short email a week: newly opened courses and deadlines coming up. Every email has an unsubscribe link."
FUNCTION_URL = CFG["supabase_url"].rstrip("/") + "/functions/v1/" + CFG["subscribe_function"]
NL_ACTION = FUNCTION_URL
WELCOME = bool(CFG["email"]["welcome_enabled"])  # copy follows the switch; the function has its own WELCOME_ENABLED setting
NL_OK = ("Thanks, you are on the list. A short welcome email is on its way; then one email a week." if WELCOME
         else "Thanks, you are on the list. The first email you get will be a weekly issue.")
HONEYPOT = ('<input type="text" name="cb_hp_note" value="" tabindex="-1" autocomplete="off" aria-hidden="true" '
            'style="position:absolute;left:-9999px;width:1px;height:1px;opacity:0">')  # anti-spam trap: people never see it
NO_BAR_PAGES = ("newsletter.html", "privacy.html", "404.html", "unsubscribe.html")

def signup_js():
    return ("<script>/* newsletter form: sends only the email address; no cookies, no storage */"
            "if(!window.cbSub){window.cbSub=function(f){var m=f.parentNode.querySelector('.nl-msg'),b=f.querySelector('button'),"
            "ok=f.getAttribute('data-ok'),em=f.querySelector('input[type=email]');"
            "var hp=f.querySelector('input[name=cb_hp_note]');if(hp&&hp.value){m.textContent=ok;f.reset();return false;}"
            "if(!em.checkValidity()){m.textContent='Please enter a valid email address.';return false;}"
            "b.disabled=true;m.textContent='Sending\u2026';"
            "fetch(f.action,{method:'POST',headers:{'Content-Type':'application/json'},"
            "body:JSON.stringify({email:em.value.trim(),cb_hp_note:''})}).then(function(r){"
            "if(r.ok){m.textContent=ok;f.reset();}"
            "else if(r.status===400){m.textContent='Please enter a valid email address.';}"
            "else if(r.status===429){m.textContent='Too many sign-ups from this connection. Please try again in an hour.';}"
            "else{m.textContent='Something went wrong. Please try again.';}})"
            ".catch(function(){m.textContent='Network error. Please try again.';}).then(function(){b.disabled=false;});return false;};}</script>")

def signup_form(fid, heading=True):
    h = '<h2 class="nl-h">Get new courses and deadlines by email</h2>' if heading else ""
    return (f'<div class="nl-box" id="{fid}">{h}<p class="nl-promise">{e(NL_PROMISE)}</p>'
            f'<form class="nl" action="{e(NL_ACTION)}" method="post" data-ok="{e(NL_OK)}" onsubmit="return cbSub(this)">'
            f'<label class="sr" for="{fid}-email">Email address</label>'
            f'<input type="email" id="{fid}-email" name="email" placeholder="you@example.com" required maxlength="254" autocomplete="email">'
            f'{HONEYPOT}<button type="submit">Subscribe</button></form>'
            f'<p class="small nl-msg" aria-live="polite">Free. We store your email, when you signed up and an unsubscribe code. <a href="{{R}}privacy.html">Privacy</a></p></div>')

def unsubscribe_body():
    # The link in every email lands here with ?t=<token>; the page posts the token once on load. One click, no form.
    return ('<main><div class="wrap prose"><h1>Unsubscribe</h1><p id="unsub-msg" aria-live="polite">Removing your address\u2026</p>'
            f'<p><a href="{{R}}index.html">Back to the course board</a></p></div></main>'
            "<script>(function(){var m=document.getElementById('unsub-msg');"
            "var t=new URLSearchParams(location.search).get('t')||'';"
            "if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(t)){m.textContent='This unsubscribe link is incomplete. Please use the full link from the email.';return;}"
            f"fetch({json.dumps(FUNCTION_URL)},{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{action:'unsubscribe',token:t}})}})"
            ".then(function(r){return r.json().then(function(j){return [r.ok,j]})}).then(function(x){"
            "if(x[0]&&x[1].ok){m.textContent=x[1].removed?'Done. Your address has been deleted from the CoachBadge list. You will get no more emails.':"
            "'This address is not on the list any more. You will get no more emails.';}"
            "else{m.textContent='Something went wrong. Please try the link again.';}})"
            ".catch(function(){m.textContent='Network error. Please try the link again.';});})();</script>")

def sticky_bar(r):
    return (f'<div class="nl-bar" id="nl-bar"><span>{e(NL_PROMISE.split(". Every")[0])}.</span>'
            f'<a class="nl-bar-go" href="{r}newsletter.html">Subscribe</a><button type="button" class="nl-bar-x" aria-label="Close">\u00d7</button></div>'
            "<script>(function(){var b=document.getElementById('nl-bar');if(!b)return;var closed=false,vis=0;"
            "function u(){var s=!closed&&vis===0;b.hidden=!s;document.body.classList.toggle('has-bar',s)}"
            "b.querySelector('.nl-bar-x').addEventListener('click',function(){closed=true;u()});"
            "var f=document.querySelector('.nl-box');var go=b.querySelector('.nl-bar-go');"
            "if(f){go.addEventListener('click',function(ev){ev.preventDefault();f.scrollIntoView({behavior:'smooth',block:'center'});"
            "var i=f.querySelector('input[type=email]');if(i)setTimeout(function(){i.focus({preventScroll:true})},400)});"
            "if('IntersectionObserver' in window){new IntersectionObserver(function(es){es.forEach(function(x){vis+=x.isIntersecting?1:-1;if(vis<0)vis=0});u()})"
            ".observe(f)}}u()})();</script>")

def page(path, title, desc, body, jsonld=None, extra_head="", robots="index,follow"):
    depth = path.count("/"); r = "../" * depth
    url = BASE + (path[:-10] if path.endswith("index.html") else path)
    full_title = title if title.startswith(BRAND) else f"{title} | {BRAND}"
    ld = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (jsonld or []))
    nav = [("index.html", "Courses"), ("countries.html", "Countries"), ("levels.html", "Levels"),
           ("methodology.html", "Methodology"), ("about.html", "About")]
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(full_title)}</title><meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}"><meta name="robots" content="{robots}">
<meta property="og:type" content="website"><meta property="og:site_name" content="{e(BRAND)}">
<meta property="og:title" content="{e(full_title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{e(url)}">
<meta name="twitter:card" content="summary"><link rel="icon" href="{r}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{r}style.css">{extra_head}{ld}</head>
<body><header class="top"><div class="wrap"><a class="brand" id="wordmark" href="{r}index.html" aria-label="{e(BRAND)} home">{BADGE}<span>{e(CFG['wordmark'][:5])}<b>{e(CFG['wordmark'][5:])}</b></span></a>
<nav class="main">{''.join(f'<a href="{r}{h}">{t}</a>' for h, t in nav)}</nav></div></header>
{body.replace('{R}', r)}
<footer><div class="wrap"><p><strong>{e(BRAND)}</strong> · {e(CFG['tagline'])}.</p>
<p>{e(CFG['disclaimer'])} Course details come from each provider's own pages and can change at any time; always confirm with the provider before you apply.</p>
<p><a href="{r}methodology.html">Methodology</a> · <a href="{e(CFG['corrections_url'])}">Report a correction</a> · <a href="{r}newsletter.html">Newsletter</a> · <a href="{r}privacy.html">Privacy</a> · <a href="{r}terms.html">Terms</a> · <a href="{r}data/courses.json">Data (JSON)</a></p>
<p class="small" style="color:#9fb0bd">Data last checked {fdate(DATA['generated'])}. © {TODAY.year} {e(BRAND)}. All rights reserved.</p></div></footer>
{"" if path in NO_BAR_PAGES else sticky_bar(r)}{signup_js() if 'cbSub(this)' in body else ""}{counter_js()}</body></html>"""
    out = os.path.join(DIST, path); os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(doc)
    return url

def tag(st): return f'<span class="tag s-{st}">{STATUS_LABEL[st]}</span>'

def when(c):
    if c.get("start_date"):
        s = fdate(c["start_date"])
        return s + (" – " + fdate(c["end_date"]) if c.get("end_date") else "")
    return ""

def apply_text(c):
    if c.get("deadline"): return "Deadline " + fdate(c["deadline"])
    return c.get("application_window") or ""

def card(c, r):
    st = c["display_status"]
    rows = [("Provider", e(c["provider"])), ("Where", e(c.get("location") or c["country"])), ("Apply", e(apply_text(c)) or "See source"),
            ("Starts", e(when(c)) or "See source"), ("Price", e(price_text(c))),
            ("Format", FORMAT_LABEL.get(c.get("format"))), ("Language", e(c.get("language") or ""))]
    return (f'<article class="card {c["sport"]}"><div>{tag(st)} <span class="small">{e(c["level"])} · {e(c["country"])}</span></div>'
            f'<h3>{e(c["title"])}</h3><dl>' + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows) +
            f'</dl><p class="small"><a href="{e(c["source_url"])}" rel="nofollow noopener">Source</a> · checked {fdate(c["fetched_at"])}</p></article>')

def table(courses, r, with_filters=True):
    def opts(name, vals): return f'<label>{name}<select data-f="{name.lower()}"><option value="">All</option>' + "".join(f'<option value="{e(v)}">{e(l)}</option>' for v, l in vals) + "</select></label>"
    f = ""
    if with_filters:
        f = ('<div class="filters" role="search">' + (opts("Sport", [(sp, sp.capitalize()) for sp in SPORTS]) if len(SPORTS) > 1 else "") +
             opts("Level", [(l, l) for l in sorted({c["level"] for c in courses})]) +
             opts("Country", [(x, x) for x in sorted({c["country"] for c in courses})]) +
             opts("Format", [(k or "none", v) for k, v in FORMAT_LABEL.items() if any(c.get("format") == k for c in courses)]) +
             opts("Price", [("listed", "Price listed"), ("none", "Price not listed")]) +
             opts("Status", [(k, v) for k, v in STATUS_LABEL.items() if any(c["display_status"] == k for c in courses)]) +
             f'<p class="small" style="align-self:end;margin:0"><span class="count" id="shown">{len(courses)}</span> of {len(courses)} courses</p></div>')
    rows = []
    for c in courses:
        st = c["display_status"]
        rows.append(f'<tr class="{st}" data-sport="{c["sport"]}" data-level="{e(c["level"])}" data-country="{e(c["country"])}" '
                    f'data-format="{c.get("format") or "none"}" data-price="{"listed" if fprice(c.get("price")) else "none"}" data-status="{st}">'
                    f'<td>{tag(st)}</td><td><strong>{e(c["title"])}</strong><br><span class="small">{e(c["provider"])} · {e(c.get("location") or "")}</span></td>'
                    f'<td>{e(c["level"])}</td><td>{e(c["country"])}</td><td>{e(apply_text(c))}</td><td>{e(when(c))}</td>'
                    f'<td>{e(price_text(c))}</td><td class="hide-sm">{FORMAT_LABEL.get(c.get("format"))}</td><td class="hide-sm">{e(c.get("language") or "")}</td>'
                    f'<td><a href="{e(c["source_url"])}" rel="nofollow noopener">Source</a><br><span class="small">{fdate(c["fetched_at"])}</span></td></tr>')
    js = """<script>(function(){var s=[].slice.call(document.querySelectorAll('.filters select')),rows=[].slice.call(document.querySelectorAll('table.courses tbody tr'));
function go(){var n=0;rows.forEach(function(r){var ok=s.every(function(x){return !x.value||r.dataset[x.dataset.f]===x.value});r.hidden=!ok;if(ok)n++});var c=document.getElementById('shown');if(c)c.textContent=n}
s.forEach(function(x){x.addEventListener('change',go)});})();</script>""" if with_filters else ""
    return (f + '<div style="overflow-x:auto"><table class="courses"><thead><tr><th>Status</th><th>Course</th><th>Level</th><th>Country</th>'
            '<th>Apply</th><th>Dates</th><th>Price</th><th class="hide-sm">Format</th><th class="hide-sm">Language</th><th>Source</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>" + js)

def course_ld(c):
    d = {"@type": "Course", "name": c["title"], "description": f'{c["level"]} coaching course run by {c["provider"]} ({c["country"]}).',
         "provider": {"@type": "Organization", "name": c["provider"]}, "url": c["source_url"], "inLanguage": c.get("language")}
    inst = {"@type": "CourseInstance"}
    if c.get("format"): inst["courseMode"] = {"residential": "onsite"}.get(c["format"], c["format"])
    if pdate(c.get("start_date")): inst["startDate"] = c["start_date"]
    if pdate(c.get("end_date")): inst["endDate"] = c["end_date"]
    if c.get("location"): inst["location"] = c["location"]
    if len(inst) > 1: d["hasCourseInstance"] = inst
    if fprice(c.get("price")): d["offers"] = {"@type": "Offer", "price": c["price"]["amount"], "priceCurrency": c["price"]["currency"], "category": "Paid", "url": c["source_url"]}
    return d

def sources_list(srcs):
    li = []
    for s in srcs:
        rd = {"yes": "read", "partial": "read, no course dates", "no": "could not be read"}[s["readable"]]
        why = s.get("reason") or s.get("note") or ""
        li.append(f'<li><a href="{e(s["url"])}" rel="nofollow noopener">{e(s["association"])}</a> – {rd}{": " + e(why) if why else ""} <span class="small">(checked {fdate(s["checked"])})</span></li>')
    return "<ul>" + "".join(li) + "</ul>"

def summary_sentence():
    cn = sorted({c["country"] for c in LIVE})
    nxt = sorted([c for c in LIVE if c.get("deadline")], key=lambda c: c["deadline"])
    s = (f"As of {fdate(DATA['generated'])}, {len(LIVE)} football coaching courses in Europe are open for applications or booking on the providers' own pages, "
         f"in {', '.join(cn)}.")
    if nxt: s += f" The next deadline is {nxt[0]['title']} ({nxt[0]['provider']}) on {fdate(nxt[0]['deadline'])}."
    return s

def build():
    if os.path.exists(DIST): shutil.rmtree(DIST)
    os.makedirs(DIST)
    shutil.copy(os.path.join(ROOT, "site", "style.css"), DIST)
    open(os.path.join(DIST, "favicon.svg"), "w").write(BADGE.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" '))
    open(os.path.join(DIST, ".nojekyll"), "w").write("")
    shutil.copy(os.path.join(ROOT, "site", "email-logo.png"), DIST)  # PNG for emails (Gmail does not show SVG)
    os.makedirs(os.path.join(DIST, "data"))
    pub = {"name": BRAND, "description": CFG["tagline"], "generated": DATA["generated"], "build_date": TODAY.isoformat(),
           "disclaimer": CFG["disclaimer"], "license": "All rights reserved. Linking and short quotes with credit and a link are welcome.",
           "courses": [{k: v for k, v in c.items()} for c in COURSES]}
    json.dump(pub, open(os.path.join(DIST, "data", "courses.json"), "w"), ensure_ascii=False, indent=1)
    urls = []
    # home
    board = "".join(card(c, "") for c in LIVE) or '<p class="note">No course is open right now on the pages we could read.</p>'
    soon = [c for c in LIVE if c["display_status"] == "closing_soon"]
    by_level = {}
    for c in LIVE: by_level.setdefault(c["level"], set()).add(c["country"])
    qa = "".join(f"<li><strong>{e(l)}:</strong> open in {e(', '.join(sorted(v)))}.</li>" for l, v in sorted(by_level.items()))
    body = f"""<section class="hero"><div class="wrap"><h1>{e(CFG['tagline'])}</h1>
<p class="answer">{e(summary_sentence())}</p>
<div class="stats"><div class="stat"><strong>{len(LIVE)}</strong>open now</div><div class="stat"><strong>{len(soon)}</strong>closing in {CLOSING_DAYS} days</div>
<div class="stat"><strong>{len(COURSES)}</strong>courses tracked</div><div class="stat"><strong>{len(ALL_SOURCES)}</strong>sources checked</div></div></div></section>
<main><div class="wrap">
{signup_form("subscribe-top")}
<h2><span class="bar"></span>Open now / closing in the next {CLOSING_DAYS} days</h2>
<p class="small">Only courses whose own page says applications or booking are open, or whose booking calendar shows free places. Sorted by deadline, then start date.</p>
<div class="board">{board}</div>
<h2><span class="bar"></span>Quick answers</h2><ul>{qa}</ul>
<p class="small">Many associations publish dates late or only inside members' portals. Countries with no open course are not necessarily closed: see each <a href="countries.html">country page</a> for what we could and could not read.</p>
<h2><span class="bar"></span>All tracked courses</h2>
{table(COURSES, "")}
</div></main>"""
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": BRAND, "url": BASE, "description": CFG["tagline"]},
          {"@context": "https://schema.org", "@type": "ItemList", "name": "Open coaching courses", "numberOfItems": len(LIVE),
           "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": course_ld(c)} for i, c in enumerate(LIVE)]}]
    urls.append(page("index.html", f"{BRAND}: {CFG['tagline']}", summary_sentence()[:300], body, ld))
    # countries
    items = []
    for ct in COUNTRIES:
        cs = [c for c in COURSES if c["country"] == ct]; live = [c for c in cs if c["display_status"] in ("open", "closing_soon")]
        srcs = [s for s in ALL_SOURCES if s["country"] == ct]
        items.append(f'<li><a href="country/{slug(ct)}.html">{e(ct)} <span class="small">({len(live)} open / {len(cs)})</span></a></li>')
        ans = (f"{len(live)} of {len(cs)} tracked coaching courses in {ct} are open right now." if cs else
               f"We have not found a course in {ct} with dates we could verify.")
        b = (f'<section class="hero"><div class="wrap"><h1>Coaching courses in {e(ct)}</h1><p class="answer">{e(ans)}</p></div></section>'
             f'<main><div class="wrap">' + (f'<div class="board">{"".join(card(c, "../") for c in live)}</div><h2><span class="bar"></span>All courses</h2>{table(cs, "../")}' if cs else "")
             + (f'<h2><span class="bar"></span>Sources for {e(ct)}</h2>{sources_list(srcs)}' if srcs else "") + "</div></main>")
        urls.append(page(f"country/{slug(ct)}.html", f"Coaching courses in {ct}", f"{ans} Football coaching courses with deadlines and prices.", b,
                         [{"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": course_ld(c)} for i, c in enumerate(cs)]}]))
    urls.append(page("countries.html", "Coaching courses by country", "Football coaching courses by country.",
                     f'<main><div class="wrap"><h1>Courses by country</h1><ul class="pill-list">{"".join(items)}</ul></div></main>'))
    # levels
    items = []
    for lv in LEVELS:
        cs = [c for c in COURSES if c["level"] == lv]; live = [c for c in cs if c["display_status"] in ("open", "closing_soon")]
        items.append(f'<li><a href="level/{slug(lv)}.html">{e(lv)} <span class="small">({len(live)} open / {len(cs)})</span></a></li>')
        ans = f"{len(live)} {lv} courses are open right now" + (f", in {', '.join(sorted({c['country'] for c in live}))}." if live else ".")
        b = (f'<section class="hero"><div class="wrap"><h1>{e(lv)} courses</h1><p class="answer">{e(ans)}</p></div></section>'
             f'<main><div class="wrap"><div class="board">{"".join(card(c, "../") for c in live)}</div><h2><span class="bar"></span>All {e(lv)} courses</h2>{table(cs, "../")}</div></main>')
        urls.append(page(f"level/{slug(lv)}.html", f"{lv} coaching courses in Europe", ans + " Deadlines, dates and prices.", b,
                         [{"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": course_ld(c)} for i, c in enumerate(cs)]}]))
    urls.append(page("levels.html", "Coaching courses by level", "UEFA C, B, A, Pro, Elite Youth and goalkeeper coaching courses.",
                     f'<main><div class="wrap"><h1>Courses by level</h1><ul class="pill-list">{"".join(items)}</ul></div></main>'))
    # methodology
    unread = [s for s in ALL_SOURCES if s["readable"] == "no"]
    prose = lambda h, t, d, x: urls.append(page(h, t, d, f'<main><div class="wrap prose"><h1>{e(t)}</h1>{x}</div></main>'))
    prose("methodology.html", "Methodology", "Where CoachBadge data comes from, how often it is checked and how to report a correction.", f"""
<p>{e(BRAND)} lists coaching courses only from pages published by the football associations themselves, their regional or district associations,
and academies those associations run. We do not use forums, social posts or search-result snippets.</p>
<h2>What every entry shows</h2><p>Provider, country, level, application window or deadline, start date, price, language, format (in person, online or blended),
status, a link to the source page and the date we last checked it. If a page does not state something, we leave it blank instead of guessing.</p>
<h2>How status is decided</h2><ul>
<li><strong>Open</strong>: the page says applications or booking are open, or its booking calendar shows free places.</li>
<li><strong>Closing soon</strong>: open, with a stated deadline within {CLOSING_DAYS} days.</li>
<li><strong>Full / waitlist</strong>: the page says the course is fully booked.</li>
<li><strong>Upcoming</strong>: the page announces a future application window.</li>
<li><strong>Closed</strong>: the stated deadline has passed, or the page says applications are closed.</li>
<li><strong>Check provider</strong>: the page lists the course but does not say whether you can apply now.</li></ul>
<p>We keep the exact sentence from the page that supports each status and date, so every claim can be traced back.</p>
<h2>How often we check</h2><p>Every source is re-read once a week by a small script that identifies itself as CoachBadgeBot, follows each site's robots.txt and waits between requests.
Changes are reviewed by a person before they appear here; nothing is published automatically.</p>
<h2>Sources we could not read</h2><p>Some sites block automated reading or load their course lists with JavaScript or behind a login. We respect that and do not work around it, so these countries may have courses we do not list yet:</p>
{sources_list(unread)}
<h2>Corrections</h2><p>Spotted something wrong or missing? <a href="{e(CFG['corrections_url'])}">Open a correction</a> with the course and a link to the provider's page. Corrections are public GitHub issues, so please do not include personal details.</p>
<h2>All sources</h2>{sources_list(ALL_SOURCES)}""")
    prose("about.html", "About CoachBadge", f"{BRAND}: {CFG['tagline']}.", f"""
<p>{e(BRAND)} is an independent board of football coaching courses in Europe, from UEFA C to UEFA Pro, including Elite Youth and goalkeeper courses where they are listed.</p>
<p>Coaching course dates, deadlines and prices are scattered across dozens of football association websites in many languages. {e(BRAND)} puts them in one place, with the deadline, the price and a link to the page where you actually apply.</p>
<p>{e(CFG['disclaimer'])} We do not run courses, take applications or sell places. Always confirm details with the provider.</p>
<p>See the <a href="methodology.html">methodology</a> for how the data is collected.</p>""")
    prose("privacy.html", "Privacy", f"{BRAND} privacy notice: what the newsletter stores and how to unsubscribe.", f"""
<p>{e(BRAND)} does not use cookies, does not store anything in your browser and does not run advertising or analytics trackers.</p>
<h2>Newsletter</h2>
<p><strong>What we store:</strong> your email address, the time you signed up, a random unsubscribe code and the time the welcome email was sent. Nothing else: no name, no browser details.</p>
<p><strong>Abuse protection:</strong> to limit sign-ups to five per connection per hour, the sign-up service keeps a one-way hash of your IP address combined with the current hour (not the address itself), and deletes it after two hours.</p>
<p><strong>Why:</strong> to send you the weekly email you asked for, with newly opened courses and deadlines coming up. We do not sell or share the list, and we do not use it for anything else.</p>
<p><strong>Where:</strong> the list is kept in a database run by Supabase, in its EU (Frankfurt) region. Only the site team can read it; the sign-up form can add an address but cannot read the list.</p>
<p><strong>Sending:</strong> emails are sent through AgentMail, an email service, from {e(CFG['email']['from_address'])}. {"You get one welcome email when you sign up, then the weekly email." if WELCOME else "You get the weekly email; there is no welcome or confirmation email for now."} Your address is passed to AgentMail only to deliver them.</p>
<p><strong>How to unsubscribe:</strong> every email has a one-click unsubscribe link (and an unsubscribe header your mail app can use). It deletes your address, sign-up time and unsubscribe code straight away and keeps no record of the request.</p>
<h2>Visits</h2>
<p>The pages include a tiny visit counter that is currently switched off. If it is ever switched on, it would only send the page address, with no cookies or identifiers, and it stays off when your browser sends Do Not Track or Global Privacy Control, or when the page is loaded by an automated browser.</p>
<p>The site is hosted on GitHub Pages. GitHub may log technical data such as IP addresses to run and secure the service; see GitHub's privacy statement.</p>
<p>Corrections are sent as public GitHub issues, so please do not include personal details in them.</p>""")
    prose("terms.html", "Terms", f"{BRAND} terms of use.", f"""
<p>© {TODAY.year} {e(BRAND)}. All rights reserved.</p>
<p>You are welcome to link to any page and to quote short extracts, as long as you credit {e(BRAND)} and link to the page you quote. Please do not republish the data set in bulk without permission.</p>
<p>Course information is collected from providers' own pages and can be incomplete or out of date. It is provided as is, without any warranty. Always check with the provider before applying, paying or travelling.</p>
<p>{e(CFG['disclaimer'])} Association and competition names are used only to describe their courses.</p>""")
    prose("newsletter.html", "Newsletter", f"{BRAND} weekly email: newly opened coaching courses and deadlines coming up. Free, with an unsubscribe link in every email.", f"""
<p>{e(NL_PROMISE)}</p>
{signup_form("subscribe", heading=False)}
<h2>What you get</h2><ul>
<li>Courses whose own page has newly opened applications or booking since the last email.</li>
<li>Deadlines coming up, with the price and a link to the provider's page.</li></ul>
<p>Each issue follows the weekly review of every source described in the <a href="methodology.html">methodology</a>. {"You get a short welcome email when you sign up." if WELCOME else ""}</p>
<p>See <a href="privacy.html">privacy</a> for what we store and how to unsubscribe.</p>""")
    page("unsubscribe.html", "Unsubscribe", f"Unsubscribe from the {BRAND} email.", unsubscribe_body(), robots="noindex,nofollow")  # not in the sitemap
    page("404.html", "Page not found", "Page not found.", '<main><div class="wrap"><h1>Page not found</h1><p><a href="https://cstath71.github.io/coachbadge/">Back to the course board</a></p></div></main>')
    # robots, sitemap, llms
    open(os.path.join(DIST, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n")
    open(os.path.join(DIST, "sitemap.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        "".join(f"<url><loc>{e(u)}</loc><lastmod>{DATA['generated']}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    lv_lines = "\n".join(f"- [{lv}]({BASE}level/{slug(lv)}.html)" for lv in LEVELS)
    ct_lines = "\n".join(f"- [{ct}]({BASE}country/{slug(ct)}.html)" for ct in COUNTRIES)
    open(os.path.join(DIST, "llms.txt"), "w").write(f"""# {BRAND}

> {CFG['tagline']}.

{summary_sentence()}

{BRAND} lists football coaching courses in Europe: UEFA C, B, A, Pro, Elite Youth and goalkeeper courses.
Each entry has provider, country, level, deadline or application window, start date, price, language, format, status, a source link and the date it was last checked.
Data comes only from the associations' own pages and is re-checked weekly; changes are reviewed by a person before publishing.
{CFG['disclaimer']}
When citing, please credit {BRAND} and link to the page, and tell readers to confirm with the provider.

## Main pages
- [Open courses board]({BASE})
- [Methodology]({BASE}methodology.html)
- [Data as JSON]({BASE}data/courses.json)

## By level
{lv_lines}

## By country
{ct_lines}
""")
    print("built", len(urls), "pages;", len(LIVE), "live;", len(COURSES), "courses")

if __name__ == "__main__":
    build()
