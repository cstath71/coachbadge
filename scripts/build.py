"""Build the static site into dist/. Usage: python3 scripts/build.py [--today YYYY-MM-DD]"""
import datetime, html, json, os, re, shutil, sys, unicodedata
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
CFG = json.load(open(os.path.join(ROOT, "config", "site.json")))
DATA = json.load(open(os.path.join(ROOT, "data", "courses.json")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import enabled as enabled_sources
import seo
from seo import and_list
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
_DIP = os.path.join(ROOT, "data", "diplomas.yaml")
DIPLOMAS = (yaml.safe_load(open(_DIP, encoding="utf-8")) or {}) if os.path.exists(_DIP) else {}  # background info, never courses
COUNTRIES = sorted({c["country"] for c in COURSES} | {s["country"] for s in ALL_SOURCES})
LEVELS = sorted({c["level"] for c in COURSES})
SPORTS = sorted({c["sport"] for c in COURSES})

# Coach-shield emblem: the mockup Gus picked (assets/coachbadge-mockup.jpg -> site/logo.png via scripts/make_images.py), logo on the LEFT.
def badge(r): return f'<img class="logo" src="{r}logo.png" width="40" height="40" alt="{e(BRAND)} logo">'

def counter_js():
    # Anonymous page counter (26 Oct 2026; supabase/functions/coachbadge-hit): sends the page path, the referrer (the function keeps
    # only its domain) and any utm_ tags. No cookies, no storage, no ids. Skipped with Do Not Track / GPC, automated browsers and off-site hosts.
    ep = json.dumps(CFG.get("counter_endpoint", ""))
    host = json.dumps(BASE.split("/")[2])
    return ("<script>/* page counter: anonymous daily totals only; no cookies, no storage, no ids */"
            f"(function(){{try{{var E={ep};if(!E)return;var n=navigator;if(n.webdriver)return;"
            "if(n.doNotTrack=='1'||window.doNotTrack=='1'||n.globalPrivacyControl)return;"
            f"if(location.hostname!=={host})return;if(/bot|crawl|spider|headless/i.test(n.userAgent))return;"
            "var q=new URLSearchParams(location.search),d=JSON.stringify({p:location.pathname,r:document.referrer,us:q.get('utm_source'),um:q.get('utm_medium'),uc:q.get('utm_campaign')});"
            "if(n.sendBeacon)n.sendBeacon(E,new Blob([d],{type:'text/plain'}));else fetch(E,{method:'POST',body:d,keepalive:true,mode:'no-cors'});}catch(x){}})();</script>")

# ---- newsletter (24 Oct 2026): the forms post to the coachbadge-subscribe Edge Function (honeypot, de-duplication,
# rate limit, welcome email via Resend). No key of any kind is in the site. Removal is by the per-subscriber token link only.
NL_PROMISE = "One free short email a week: newly opened courses and deadlines coming up. Every email has an unsubscribe link."
FUNCTION_URL = CFG["supabase_url"].rstrip("/") + "/functions/v1/" + CFG["subscribe_function"]
NL_ACTION = FUNCTION_URL
WELCOME = bool(CFG["email"]["welcome_enabled"])  # copy follows the switch; the function has its own WELCOME_ENABLED setting
NL_OK = ("Thanks, you are on the list. A short welcome email is on its way; then one email a week." if WELCOME
         else "Thanks, you are on the list. The first email you get will be a weekly issue.")
HONEYPOT = ('<input type="text" name="cb_hp_note" value="" tabindex="-1" autocomplete="off" aria-hidden="true" '
            'style="position:absolute;left:-9999px;width:1px;height:1px;opacity:0">')  # anti-spam trap: people never see it
RESOURCES = CFG.get("resources", [])
DISCLOSURE = CFG["affiliate_disclosure"]
REL_AFF = "sponsored noopener"
def resource_links(r, cls="res-list"):
    return (f'<ul class="{cls}">' + "".join(f'<li><a href="{e(x["url"])}" rel="{REL_AFF}" target="_blank">{e(x["name"])}</a>: {e(x["desc"])}</li>' for x in RESOURCES) + "</ul>")
def resources_box(r):
    """Small labelled block for course pages: affiliate links plus the disclosure, kept apart from the course data."""
    if not RESOURCES: return ""
    return (f'<aside class="resources" aria-labelledby="res-h"><h2 id="res-h"><span class="bar"></span>Coaching resources</h2>'
            f'<p class="small">Tools and learning material for coaches, separate from the course listings above. <a href="{r}resources.html">All resources</a></p>'
            f'{resource_links(r)}<p class="small disclosure">{e(DISCLOSURE)}</p></aside>')
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
            f'<p><a href="{{HOME}}">Back to the course board</a></p></div></main>'
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

VERIFY = [("google-site-verification", CFG.get("google_site_verification", "")), ("msvalidate.01", CFG.get("msvalidate", ""))]
OG_IMAGE = BASE + "og.png"; OG_ALT = f"{BRAND}: {CFG['tagline']}"
PAGES = []  # (url, title, description, lastmod) of every indexable page, for sitemap.xml and llms.txt

def page(path, title, desc, body, jsonld=None, extra_head="", robots="index,follow", crumbs=None, lastmod=None):
    """crumbs: [(name, root-relative path)] ending with this page; adds a visible breadcrumb trail and BreadcrumbList."""
    depth = path.count("/"); r = "../" * depth; home = r or "./"
    url = BASE + (path[:-10] if path.endswith("index.html") else path)
    full_title = title if title.startswith(BRAND) else f"{title} | {BRAND}"
    lds = list(jsonld or []) + ([seo.breadcrumb_ld(BASE, crumbs)] if crumbs else [])
    ld = "".join(seo.ld_script(x) for x in lds)
    verify = "".join(f'<meta name="{k}" content="{e(v)}">' for k, v in VERIFY if v)
    crumb_nav = seo.breadcrumb_html(crumbs, r) if crumbs else ""
    nav = [("", "Courses"), ("countries.html", "Countries"), ("levels.html", "Levels"),
           ("methodology.html", "Methodology"), ("about.html", "About")]
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(full_title)}</title><meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}"><meta name="robots" content="{robots}">{verify}
<meta property="og:type" content="website"><meta property="og:site_name" content="{e(BRAND)}"><meta property="og:locale" content="en_GB">
<meta property="og:title" content="{e(full_title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{e(OG_IMAGE)}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="{e(OG_ALT)}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(full_title)}"><meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{e(OG_IMAGE)}"><meta name="twitter:image:alt" content="{e(OG_ALT)}">
<link rel="icon" href="{r}favicon.ico" sizes="48x48"><link rel="icon" href="{r}favicon.png" type="image/png" sizes="32x32"><link rel="apple-touch-icon" href="{r}apple-touch-icon.png">
<link rel="stylesheet" href="{r}style.css">{extra_head}{ld}</head>
<body><header class="top"><div class="wrap"><a class="brand" id="wordmark" href="{home}" aria-label="{e(BRAND)} home">{badge(r)}<span>{e(CFG['wordmark'][:5])}<b>{e(CFG['wordmark'][5:])}</b></span></a>
<nav class="main">{''.join(f'<a href="{(r + h) or "./"}">{t}</a>' for h, t in nav)}</nav></div></header>
{crumb_nav}{body.replace('{HOME}', home).replace('{R}', r)}
<footer><div class="wrap"><p><strong>{e(BRAND)}</strong> · {e(CFG['tagline'])}.</p>
<p>{e(CFG['disclaimer'])} Course details come from each provider's own pages and can change at any time; always confirm with the provider before you apply.</p>
<p><a href="{r}methodology.html">Methodology</a> · <a href="{e(CFG['corrections_url'])}">Report a correction</a> · <a href="{r}newsletter.html">Newsletter</a> · <a href="{r}resources.html">Resources</a> · <a href="{r}privacy.html">Privacy</a> · <a href="{r}terms.html">Terms</a> · <a href="{r}data/courses.json">Data (JSON)</a></p>
<p class="small" style="color:#9fb0bd">Data last checked {fdate(DATA['generated'])}. © {TODAY.year} {e(BRAND)}. All rights reserved.</p></div></footer>
{"" if path in NO_BAR_PAGES else sticky_bar(r)}{signup_js() if 'cbSub(this)' in body else ""}{counter_js()}</body></html>"""
    out = os.path.join(DIST, path); os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(doc)
    if robots.startswith("index"): PAGES.append((url, full_title, desc, lastmod or DATA["generated"]))
    return url

def tag(st): return f'<span class="tag s-{st}">{STATUS_LABEL[st]}</span>'

def when(c):
    if c.get("start_note"): return c["start_note"]  # e.g. 'May/June 2027' when the page gives no exact start
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
    """Course + CourseInstance + Offer, only from fields the provider's page actually gave us."""
    d = {"@type": "Course", "name": c["title"], "description": f'{c["level"]} football coaching course run by {c["provider"]} ({c["country"]}).',
         "provider": {"@type": "Organization", "name": c["provider"]}, "url": c["source_url"], "educationalLevel": c["level"]}
    if c.get("language"): d["inLanguage"] = c["language"]
    inst = {"@type": "CourseInstance"}
    if c.get("format"): inst["courseMode"] = {"residential": "onsite"}.get(c["format"], c["format"])
    if pdate(c.get("start_date")): inst["startDate"] = c["start_date"]
    if pdate(c.get("end_date")): inst["endDate"] = c["end_date"]
    if c.get("location"): inst["location"] = {"@type": "Place", "name": c["location"]}
    if len(inst) > 1: d["hasCourseInstance"] = inst
    if fprice(c.get("price")): d["offers"] = {"@type": "Offer", "price": c["price"]["amount"], "priceCurrency": c["price"]["currency"], "category": "Paid", "url": c["source_url"]}
    return d

def item_list(name, url, cs):
    return {"@context": "https://schema.org", "@type": "ItemList", "name": name, "url": url, "numberOfItems": len(cs),
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": course_ld(c)} for i, c in enumerate(cs)]}

def sources_list(srcs):
    li = []
    for s in srcs:
        rd = {"yes": "read", "partial": "read, no course dates", "browser": "read by a person in a browser", "no": "could not be read"}[s["readable"]]
        why = s.get("reason") or s.get("note") or ""
        li.append(f'<li><a href="{e(s["url"])}" rel="nofollow noopener">{e(s["association"])}</a> – {rd}{": " + e(why) if why else ""} <span class="small">(checked {fdate(s["checked"])})</span></li>')
    return "<ul>" + "".join(li) + "</ul>"

def is_live(c): return c["display_status"] in ("open", "closing_soon")
def next_deadline(cs):
    n = sorted([c for c in cs if is_live(c) and c.get("deadline")], key=lambda c: (c["deadline"], c["id"]))
    return n[0] if n else None
def counted(n, one, many=None): return f"{n} {one if n == 1 else (many or one + 's')}"
def open_clause(k, n, noun, where=""):
    """'3 of the 5 UEFA B courses CoachBadge tracks are open', with the right grammar for 0 and 1."""
    tr = f"{BRAND} tracks{where}"
    if k == 0 and n == 1: return f"the one {noun} {tr} is not open for applications or booking"
    if k == 0: return f"none of the {n} {noun}s {tr} is open for applications or booking"
    return f"{k} of the {counted(n, noun)} {tr} {'is' if k == 1 else 'are'} open for applications or booking"
def price_range(cs):
    """'£A–£B' per currency, only from prices the providers list."""
    by = {}
    for c in cs:
        if fprice(c.get("price")): by.setdefault(c["price"]["currency"], []).append(c["price"]["amount"])
    out = []
    for cur, xs in sorted(by.items()):
        lo, hi = fprice({"amount": min(xs), "currency": cur}), fprice({"amount": max(xs), "currency": cur})
        out.append(lo if lo == hi else f"{lo} to {hi}")
    return out
GEN = fdate(DATA["generated"])

def summary_sentence():
    cn = sorted({c["country"] for c in LIVE})
    nxt = next_deadline(LIVE)
    s = (f"As of {GEN}, {len(LIVE)} football coaching courses in Europe are open for applications or booking on the providers' own pages, "
         f"in {and_list(cn)}.")
    if nxt: s += f" The next deadline is {nxt['title']} ({nxt['provider']}) on {fdate(nxt['deadline'])}."
    return s

def scope_sentence():
    return (f"{BRAND} tracks {counted(len(COURSES), 'course')} at {counted(len(LEVELS), 'level')} from {counted(len(ALL_SOURCES), 'source page')} "
            f"in {counted(len(COUNTRIES), 'country', 'countries')}, re-checked every week.")

def count_badge(live, cs):
    """Short label for listings. Never shows a bare zero: a country with nothing we could verify says 'Check association'."""
    if live: return f"{len(live)} open / {len(cs)}"
    if cs: return f"{len(cs)} tracked, none open"
    return "Check association"

def plain_reason(srcs):
    """Why a country has no open course, in plain words, from its sources' reasons and notes."""
    why = []
    for x in srcs:
        t = (x.get("reason") or x.get("note") or "").strip().rstrip(".")
        if t: t = f"{x['association']}: {t[0].lower() + t[1:] if t[:2] != t[:2].upper() else t}"
        if t and t not in why: why.append(t)
    if not why: return "We have not found course dates on the pages we can read."
    return " ".join(w + "." for w in why)

def empty_state(srcs, r, scope=""):
    """Shown on a country or level page with no open course: what to do instead, with links to the association's course pages."""
    links = "".join(f'<li><a href="{e(x["url"])}" rel="nofollow noopener">{e(x["association"])}</a></li>' for x in srcs)
    return (f'<section class="note empty-state" id="no-open-courses"><h2>No open courses right now</h2>'
            f'<p>We could not find a course{e(scope)} that is open for applications or booking on the pages we can read. '
            "That does not mean there are none: associations often publish dates late, or only inside a members' login.</p>"
            + (f'<p><strong>Why:</strong> {e(plain_reason(srcs))}</p>' if srcs else "")
            + (f"<p>Check the association's course pages:</p><ul>{links}</ul>" if srcs else f'<p>See the <a href="{r}countries.html">country pages</a> for each association\'s course pages.</p>')
            + "</section>")

def diploma_cost(d):
    """The cost as the page states it, and how the registration fee relates to it (from the page's own breakdown)."""
    sym = CUR.get(d.get("currency"), "")
    if d.get("cost") is None: return "Not listed"
    t = f"{sym}{d['cost']:,}" if sym else f"{d['cost']:,} {d.get('currency') or ''}".strip()
    fee = d.get("registration_fee")
    if fee is not None:
        f = f"{sym}{fee:,}" if sym else f"{fee:,} {d.get('currency') or ''}".strip()
        t += f", including the {f} registration fee" if d.get("registration_included") else f", plus {f} registration fee"
    return t

def diplomas_box(ct):
    """National diplomas and the UEFA level each counts as. Information only: not courses, no Course JSON-LD."""
    info = DIPLOMAS.get(ct)
    if not info or not info.get("diplomas"): return ""
    rows = "".join(f'<tr><td><strong>{e(d["short"])}</strong> – {e(d["name"])}</td><td>{e(d["uefa"])}</td>'
                   f'<td>{e(diploma_cost(d))}</td><td>{e(d.get("where") or "Not stated")}</td>'
                   f'<td><a href="{e(d["url"])}" rel="nofollow noopener">{e(d["short"])} page</a></td></tr>' for d in info["diplomas"])
    return (f'<section class="diplomas" id="diplomas"><h2><span class="bar"></span>{e(info["title"])}</h2>'
            f'<p>{e(info["note"])}</p>'
            '<div style="overflow-x:auto"><table class="info"><thead><tr><th>Diploma</th><th>UEFA level (as stated)</th><th>Cost (as stated)</th><th>Where</th><th>Source</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div><p class="small">Checked {e(fdate(info["fetched_at"]))}. These are not dated courses, so they are not counted as courses on this site.</p></section>')

def country_summary(ct, cs, srcs):
    live = [c for c in cs if is_live(c)]
    if not cs:
        s = f"As of {GEN}, {BRAND} has not found a football coaching course in {ct} with dates it could verify on the provider's pages."
    else:
        s = f"As of {GEN}, {open_clause(len(live), len(cs), 'football coaching course', ' in ' + ct)}"
        lv = sorted({c["level"] for c in live})
        s += (f" ({and_list(lv)})." if lv else ".")
        n = next_deadline(cs)
        if n: s += f" The next deadline is {n['title']} ({n['provider']}) on {fdate(n['deadline'])}."
    unread = [x for x in srcs if x["readable"] == "no"]
    if srcs: s += f" We check {counted(len(srcs), 'source page')} for {ct}" + (f"; {len(unread)} could not be read." if unread else ".")
    return s

def level_summary(lv, cs):
    live = [c for c in cs if is_live(c)]
    s = f"As of {GEN}, {open_clause(len(live), len(cs), lv + ' course')}"
    cn = sorted({c["country"] for c in live})
    s += (f", in {and_list(cn)}." if cn else ".")
    n = next_deadline(cs)
    if n: s += f" The next deadline is {n['title']} ({n['provider']}) on {fdate(n['deadline'])}."
    pr = [c for c in cs if fprice(c.get("price"))]
    if cs: s += f" {len(pr)} of {len(cs)} {'lists' if len(pr) == 1 else 'list'} a price." if pr else " None lists a price."
    return s

def home_faq():
    lv = {}
    for c in COURSES: lv[c["level"]] = lv.get(c["level"], 0) + 1
    by_c = {}
    for c in LIVE: by_c[c["country"]] = by_c.get(c["country"], 0) + 1
    unread = [x for x in ALL_SOURCES if x["readable"] == "no"]
    pr = [c for c in COURSES if fprice(c.get("price"))]
    nxt = next_deadline(LIVE)
    return [
        (f"What is {BRAND}?", f"{e(BRAND)} is an independent board of football coaching courses in Europe. It collects course dates, deadlines and prices from the football associations' own pages and links to the page where you apply. {e(CFG['disclaimer'])} It does not run courses, take applications or sell places."),
        ("Which football coaching courses are open right now?",
         f"As of {GEN}, {len(LIVE)} courses are open for applications or booking: " + e(and_list([f"{n} in {k}" for k, n in sorted(by_c.items())])) + "."
         + (f" The next deadline is {e(nxt['title'])} ({e(nxt['provider'])}) on {fdate(nxt['deadline'])}." if nxt else "") + ' The board at the top of this page lists them.'),
        (f"Which coaching levels and countries does {BRAND} cover?",
         "Courses by level: " + e(and_list([f"{k} ({n})" for k, n in sorted(lv.items())])) + f". We check {counted(len(ALL_SOURCES), 'source page')} in {counted(len(COUNTRIES), 'country', 'countries')}"
         + (f"; {len(unread)} of them could not be read" if unread else "") + '. See <a href="levels.html">levels</a> and <a href="countries.html">countries</a>.'),
        ("Where does the course information come from?", 'Only from pages published by the football associations, their regional or district associations, and academies those associations run. Each entry keeps the exact sentence from the page that supports its status and dates. <a href="methodology.html">Methodology</a>.'),
        (f"How often is {BRAND} updated?", f"Every source is re-read once a week, and changes are reviewed by a person before they appear. The data was last checked on {GEN}."),
        ("Are course prices listed?", f"{len(pr)} of the {len(COURSES)} tracked courses show a price from the provider's page. Where the page states no price, the listing says \u201cNot listed\u201d instead of guessing."),
        ("How do I apply for a coaching course?", f"Through the provider. Every course links to its source page, where you apply or book. {e(BRAND)} does not take applications; always confirm dates and prices with the provider."),
        ("Is there a newsletter?", f'{e(NL_PROMISE)} <a href="newsletter.html">Sign up</a>.'),
    ]

def country_faq(ct, cs, srcs, r):
    live = [c for c in cs if is_live(c)]; n = next_deadline(cs)
    if live:
        a = f"Yes. As of {GEN}, {counted(len(live), 'course')} in {e(ct)} {'is' if len(live) == 1 else 'are'} open: " + e(and_list([f"{c['title']} ({c['provider']})" for c in live[:8]])) + (f", and {len(live) - 8} more" if len(live) > 8 else "") + "."
        if n: a += f" The next deadline is {fdate(n['deadline'])}."
    else:
        a = f"Not on the pages we could read as of {GEN}. Many associations publish dates late or only inside members' portals, so check the sources below."
    rd = {"yes": "read", "partial": "read, but without course dates", "browser": "read by a person in a browser", "no": "could not be read"}
    b = (f"From {counted(len(srcs), 'page')} published by the provider{'s' if len(srcs) != 1 else ''}: " + e(and_list([f"{x['association']} ({rd[x['readable']]})" for x in srcs])) + f". Each is re-checked weekly; last checked {fdate(max(x['checked'] for x in srcs))}."
         if srcs else f"Only from the providers' own pages; see the <a href=\"{r}methodology.html\">methodology</a>.")
    return [(f"Are there open football coaching courses in {ct}?", a), (f"Where does {BRAND} get course information for {ct}?", b)]

def level_faq(lv, cs):
    live = [c for c in cs if is_live(c)]; n = next_deadline(cs)
    by_c = {}
    for c in live: by_c[c["country"]] = by_c.get(c["country"], 0) + 1
    a = (f"As of {GEN}, {lv} courses are open in " + e(and_list([f"{k} ({v})" for k, v in sorted(by_c.items())])) + "." if live else f"None is open on the pages we could read as of {GEN}; the table below shows every {e(lv)} course we track and its status.")
    b = (f"{e(n['title'])} ({e(n['provider'])}, {e(n['country'])}) on {fdate(n['deadline'])}." if n else f"None of the open {e(lv)} courses states a deadline on its page as of {GEN}; some take applications until places are full." if live else f"No {e(lv)} course is open right now, so there is no upcoming deadline.")
    pr = [c for c in cs if fprice(c.get("price"))]; rg = price_range(cs)
    p = (f"{len(pr)} of the {len(cs)} {e(lv)} courses list a price on the provider's page: " + e(" and ".join(rg)) + ". Check each course for what the price includes."
         if pr else f"None of the {e(lv)} courses we track lists a price on the provider's page.")
    return [(f"Where can I take a {lv} course right now?", a), (f"When is the next {lv} application deadline?", b), (f"How much does a {lv} course cost?", p)]

def build():
    if os.path.exists(DIST): shutil.rmtree(DIST)
    os.makedirs(DIST); PAGES.clear()
    shutil.copy(os.path.join(ROOT, "site", "style.css"), DIST)
    open(os.path.join(DIST, ".nojekyll"), "w").write("")
    shutil.copy(os.path.join(ROOT, "site", "email-logo.png"), DIST)  # PNG for emails (Gmail does not show SVG)
    for f in ("logo.png", "og.png", "logo-512.png", "apple-touch-icon.png", "favicon.ico", "favicon.png"): shutil.copy(os.path.join(ROOT, "site", f), DIST)  # share card + structured-data logo (scripts/make_images.py)
    shutil.copy(os.path.join(ROOT, "CNAME"), DIST)  # custom domain for GitHub Pages
    open(os.path.join(DIST, seo.INDEXNOW_KEY + ".txt"), "w").write(seo.INDEXNOW_KEY)  # IndexNow ownership file
    os.makedirs(os.path.join(DIST, "data"))
    pub = {"name": BRAND, "description": CFG["tagline"], "generated": DATA["generated"], "build_date": TODAY.isoformat(),
           "disclaimer": CFG["disclaimer"], "license": "All rights reserved. Linking and short quotes with credit and a link are welcome.",
           "courses": [{k: v for k, v in c.items()} for c in COURSES]}
    json.dump(pub, open(os.path.join(DIST, "data", "courses.json"), "w"), ensure_ascii=False, indent=1)
    # home
    board = "".join(card(c, "") for c in LIVE) or '<p class="note">No course is open right now on the pages we could read.</p>'
    soon = [c for c in LIVE if c["display_status"] == "closing_soon"]
    by_level = {}
    for c in LIVE: by_level.setdefault(c["level"], set()).add(c["country"])
    qa = "".join(f"<li><strong>{e(l)}:</strong> open in {e(', '.join(sorted(v)))}.</li>" for l, v in sorted(by_level.items()))
    faq = home_faq()
    body = f"""<section class="hero"><div class="wrap"><h1>{e(CFG['tagline'])}</h1>
<p class="answer" id="summary">{e(summary_sentence())} {e(scope_sentence())}</p>
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
{seo.faq_html(faq)}
{resources_box("")}
</div></main>"""
    ld = [{"@context": "https://schema.org", "@graph": [seo.website(BASE, BRAND, CFG["tagline"]), seo.org(BASE, BRAND)]},
          item_list("Open football coaching courses", BASE, LIVE), seo.faq_ld(faq)]
    page("index.html", f"{BRAND}: {CFG['tagline']}", summary_sentence()[:300], body, ld)
    # countries
    items = []
    for ct in COUNTRIES:
        cs = [c for c in COURSES if c["country"] == ct]; live = [c for c in cs if is_live(c)]
        srcs = [x for x in ALL_SOURCES if x["country"] == ct]
        items.append(f'<li><a href="country/{slug(ct)}.html">{e(ct)} <span class="small">({count_badge(live, cs)})</span></a></li>')
        ans = country_summary(ct, cs, srcs); faq = country_faq(ct, cs, srcs, "../")
        path = f"country/{slug(ct)}.html"
        b = (f'<section class="hero"><div class="wrap"><h1>Football coaching courses in {e(ct)}</h1><p class="answer" id="summary">{e(ans)}</p></div></section>'
             f'<main><div class="wrap">'
             + (f'<h2><span class="bar"></span>Open now in {e(ct)}</h2><div class="board">{"".join(card(c, "../") for c in live)}</div>' if live else empty_state(srcs, "../", " in " + ct))
             + diplomas_box(ct)
             + (f'<h2><span class="bar"></span>All courses in {e(ct)}</h2>{table(cs, "../")}' if cs else "")
             + (f'<h2><span class="bar"></span>Sources for {e(ct)}</h2>{sources_list(srcs)}' if srcs else "")
             + seo.faq_html(faq) + resources_box("../") + "</div></main>")
        lm = max([c["fetched_at"] for c in cs] + [x["checked"] for x in srcs] or [DATA["generated"]])
        page(path, f"Football coaching courses in {ct}", f"{ans} Deadlines, dates and prices with links to each provider."[:300], b,
             ([item_list(f"Football coaching courses in {ct}", BASE + path, cs)] if cs else []) + [seo.faq_ld(faq)],
             crumbs=[(BRAND, ""), ("Countries", "countries.html"), (ct, path)], lastmod=lm)
    n_live_ct = len({c["country"] for c in LIVE})
    cdesc = f"Football coaching courses in {len(COUNTRIES)} European countries; {n_live_ct} have a course open as of {GEN}. Deadlines, dates and prices from each association's pages."
    page("countries.html", "Football coaching courses by country", cdesc,
         f'<main><div class="wrap"><h1>Football coaching courses by country</h1><p class="answer-sub">{e(cdesc)}</p><ul class="pill-list">{"".join(items)}</ul></div></main>',
         crumbs=[(BRAND, ""), ("Countries", "countries.html")])
    # levels
    items = []
    for lv in LEVELS:
        cs = [c for c in COURSES if c["level"] == lv]; live = [c for c in cs if is_live(c)]
        path = f"level/{slug(lv)}.html"
        items.append(f'<li><a href="{path}">{e(lv)} <span class="small">({count_badge(live, cs)})</span></a></li>')
        ans = level_summary(lv, cs); faq = level_faq(lv, cs)
        b = (f'<section class="hero"><div class="wrap"><h1>{e(lv)} football coaching courses in Europe</h1><p class="answer" id="summary">{e(ans)}</p></div></section>'
             f'<main><div class="wrap">' + (f'<h2><span class="bar"></span>Open now</h2><div class="board">{"".join(card(c, "../") for c in live)}</div>' if live
                                             else empty_state([x for x in ALL_SOURCES if lv in x.get("levels", [])], "../", " at " + lv))
             + f'<h2><span class="bar"></span>All {e(lv)} courses</h2>{table(cs, "../")}{seo.faq_html(faq)}{resources_box("../")}</div></main>')
        page(path, f"{lv} coaching courses in Europe", f"{ans} Deadlines, dates and prices."[:300], b,
             [item_list(f"{lv} football coaching courses", BASE + path, cs), seo.faq_ld(faq)],
             crumbs=[(BRAND, ""), ("Levels", "levels.html"), (lv, path)], lastmod=max(c["fetched_at"] for c in cs))
    ldesc = f"Football coaching courses by level: {and_list(LEVELS)}. {len(LIVE)} open as of {GEN}."
    page("levels.html", "Football coaching courses by level", ldesc,
         f'<main><div class="wrap"><h1>Football coaching courses by level</h1><p class="answer-sub">{e(ldesc)}</p><ul class="pill-list">{"".join(items)}</ul></div></main>',
         crumbs=[(BRAND, ""), ("Levels", "levels.html")])
    # methodology
    unread = [s for s in ALL_SOURCES if s["readable"] == "no"]
    prose = lambda h, t, d, x: page(h, t, d, f'<main><div class="wrap prose"><h1>{e(t)}</h1>{x}</div></main>', crumbs=[(BRAND, ""), (t, h)])
    prose("methodology.html", "Methodology", f"Where {BRAND} data comes from, how often it is checked and how to report a correction.", f"""
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
Changes are reviewed by a person before they appear here; nothing is published automatically.
A few sites refuse automated visitors but show their course pages to people. Those we read by hand in a normal browser, mark as “read by a person in a browser” and re-check by hand; the script does not visit them.</p>
<h2>Sources we could not read</h2><p>Some sites block automated reading or load their course lists with JavaScript or behind a login. We respect that and do not work around it, so these countries may have courses we do not list yet:</p>
{sources_list(unread)}
<h2>Corrections</h2><p>Spotted something wrong or missing? <a href="{e(CFG['corrections_url'])}">Open a correction</a> with the course and a link to the provider's page. Corrections are public GitHub issues, so please do not include personal details.</p>
<h2>All sources</h2>{sources_list(ALL_SOURCES)}""")
    prose("about.html", f"About {BRAND}", f"About {BRAND}, an independent board of football coaching courses in Europe, from UEFA C to UEFA Pro, built from the associations' own pages.", f"""
<p>{e(BRAND)} is an independent board of football coaching courses in Europe, from UEFA C to UEFA Pro, including Elite Youth and goalkeeper courses where they are listed.</p>
<p>Coaching course dates, deadlines and prices are scattered across dozens of football association websites in many languages. {e(BRAND)} puts them in one place, with the deadline, the price and a link to the page where you actually apply.</p>
<p>{e(CFG['disclaimer'])} We do not run courses, take applications or sell places. Always confirm details with the provider.</p>
<p>See the <a href="methodology.html">methodology</a> for how the data is collected.</p>
<h2>Affiliate links</h2><p class="disclosure">{e(DISCLOSURE)} They appear only in the clearly labelled <a href="resources.html">coaching resources</a> sections and never affect which courses are listed or how they are sorted.</p>""")
    prose("privacy.html", "Privacy", f"{BRAND} privacy notice: what the newsletter stores and how to unsubscribe.", f"""
<p>{e(BRAND)} does not use cookies, does not store anything in your browser and does not run advertising trackers. The only analytics is an anonymous page count (see Visits below).</p>
<h2>Newsletter</h2>
<p><strong>What we store:</strong> your email address, the time you signed up, a random unsubscribe code and the time the welcome email was sent. Nothing else: no name, no browser details.</p>
<p><strong>Abuse protection:</strong> to limit sign-ups to five per connection per hour, the sign-up service keeps a one-way hash of your IP address combined with the current hour (not the address itself), and deletes it after two hours.</p>
<p><strong>Why:</strong> to send you the weekly email you asked for, with newly opened courses and deadlines coming up. We do not sell or share the list, and we do not use it for anything else.</p>
<p><strong>Where:</strong> the list is kept in a database run by Supabase, in its EU (Frankfurt) region. Only the site team can read it; the sign-up form can add an address but cannot read the list.</p>
<p><strong>Sending:</strong> emails are sent through Resend, an email service, from {e(CFG['email']['from_address'])}. {"You get one welcome email when you sign up, then the weekly email." if WELCOME else "You get the weekly email; there is no welcome or confirmation email for now."} Your address is passed to Resend only to deliver them.</p>
<p><strong>How to unsubscribe:</strong> every email has a one-click unsubscribe link (and an unsubscribe header your mail app can use). It deletes your address, sign-up time and unsubscribe code straight away and keeps no record of the request.</p>
<h2>Affiliate links</h2>
<p class="disclosure">{e(DISCLOSURE)} These links carry a referral code in the address so the other site can credit {e(BRAND)}. {e(BRAND)} sets no cookies; the site you visit may set its own, under its own privacy policy.</p>
<h2>Visits</h2>
<p>We record only anonymous page counts, without cookies. For each day we keep a total per page, together with the domain of the site that linked to it (for example google.com) and any utm_ tags in the link. No IP address, browser details or identifier is stored, so a visit cannot be traced back to you. Nothing is counted when your browser sends Do Not Track or Global Privacy Control, or when the page is loaded by an automated browser. The counts are kept with Supabase, in its EU (Frankfurt) region.</p>
<p>The site is hosted on GitHub Pages. GitHub may log technical data such as IP addresses to run and secure the service; see GitHub's privacy statement.</p>
<p>Corrections are sent as public GitHub issues, so please do not include personal details in them.</p>""")
    prose("terms.html", "Terms", f"{BRAND} terms of use: linking and short quotes with credit are welcome; course details are provided as is and should be confirmed with the provider.", f"""
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
    prose("resources.html", "Coaching resources", f"Coaching tools, books and online courses for football coaches. Includes affiliate links.", f"""
<p class="disclosure"><strong>{e(DISCLOSURE)}</strong></p>
<p>Tools and learning material for football coaches. These are separate from the course board: {e(BRAND)} lists courses only from the providers' own pages, and these links never affect which courses are listed or how they are sorted.</p>
{resource_links("")}
<p class="small">Check prices and terms on each site before you buy.</p>""")
    page("unsubscribe.html", "Unsubscribe", f"Unsubscribe from the {BRAND} email.", unsubscribe_body(), robots="noindex,nofollow")  # not in the sitemap
    page("404.html", "Page not found", "Page not found.", f'<main><div class="wrap"><h1>Page not found</h1><p><a href="{BASE}">Back to the course board</a></p></div></main>', robots="noindex,follow")
    # robots, sitemap, llms (every indexable page registered itself in PAGES; noindex pages did not)
    open(os.path.join(DIST, "robots.txt"), "w").write(seo.robots_txt(BASE))
    open(os.path.join(DIST, "sitemap.xml"), "w").write(seo.sitemap_xml([(u, d) for u, _, _, d in PAGES]))
    llms = llms_txt()
    open(os.path.join(DIST, "llms.txt"), "w").write(llms)
    open(os.path.join(DIST, "llms-full.txt"), "w").write(llms_full(llms))
    print("built", len(PAGES), "indexable pages;", len(LIVE), "live;", len(COURSES), "courses")

def llms_txt():
    lv_lines = "\n".join(f"- [{lv}]({BASE}level/{slug(lv)}.html): {level_summary(lv, [c for c in COURSES if c['level'] == lv])}" for lv in LEVELS)
    ct_lines = "\n".join(f"- [{ct}]({BASE}country/{slug(ct)}.html): {count_badge([c for c in COURSES if c['country'] == ct and is_live(c)], [c for c in COURSES if c['country'] == ct])}" for ct in COUNTRIES)
    faq = "\n\n".join(f"### {q}\n{seo.text(a)}" for q, a in home_faq())
    return f"""# {BRAND}

> {CFG['tagline']}.

{summary_sentence()} {scope_sentence()}

{BRAND} lists football coaching courses in Europe from the providers' own pages. Levels in the data: {and_list(LEVELS)}.
Each entry has provider, country, level, deadline or application window, start date, price, language, format, status, a source link and the date it was last checked, plus the verbatim sentences from the source page that support it.

How the data is gathered: a small script (CoachBadgeBot) re-reads every source page once a week, follows each site's robots.txt and waits between requests. Changes are reviewed by a person before they are published; nothing is published automatically. If a page does not state something, the field is left blank instead of guessed. Sites that block automated reading or need a login are listed as "could not be read"; a few that refuse automated visitors are read by a person in a normal browser instead and marked "read by a person in a browser".
Status: "Open" only when the page says applications or booking are open (or its booking calendar shows free places); "Closing soon" means open with a deadline within {CLOSING_DAYS} days.
Data last checked: {DATA['generated']}. Update cadence: weekly.
{CFG['disclaimer']} {BRAND} does not run courses, take applications or sell places.
When citing, please credit {BRAND}, link to the page, and tell readers to confirm with the provider.

## Main pages
- [Open courses board]({BASE}): every course open now, plus all tracked courses
- [Courses by country]({BASE}countries.html)
- [Courses by level]({BASE}levels.html)
- [Methodology]({BASE}methodology.html): sources, status rules, weekly checks, corrections
- [About]({BASE}about.html)
- [Newsletter]({BASE}newsletter.html): {NL_PROMISE}
- [Coaching resources]({BASE}resources.html): tools for coaches (affiliate links, kept apart from the course data)
- [Data as JSON]({BASE}data/courses.json): every course with its fields and evidence
- [Full text for AI assistants]({BASE}llms-full.txt): every course in plain text

## By level
{lv_lines}

## By country
{ct_lines}

## FAQ

{faq}
"""

def llms_full(llms):
    out = [llms, f"\n## All {len(COURSES)} tracked courses (data of {DATA['generated']})\n"]
    for c in COURSES:
        bits = [f"status: {STATUS_LABEL[c['display_status']]}", f"provider: {c['provider']}", f"country: {c['country']}", f"level: {c['level']}"]
        if c.get("location"): bits.append(f"location: {c['location']}")
        if apply_text(c): bits.append(f"apply: {apply_text(c)}")
        if when(c): bits.append(f"dates: {when(c)}")
        bits.append(f"price: {price_text(c)}")
        if c.get("format"): bits.append(f"format: {FORMAT_LABEL[c['format']]}")
        if c.get("language"): bits.append(f"language: {c['language']}")
        bits += [f"source: {c['source_url']}", f"checked: {c['fetched_at']}"]
        out.append(f"- {c['title']}; " + "; ".join(bits))
    return "\n".join(out) + "\n"

if __name__ == "__main__":
    build()
