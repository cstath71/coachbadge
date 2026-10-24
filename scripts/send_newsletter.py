"""Build (and only when asked, send) the CoachBadge weekly email.

The issue is built only from data/courses.json and the latest reports/refresh-*.md:
  - Newly opened: courses the latest refresh added that are open on the issue date.
  - Updated open courses: courses the latest refresh modified that are open on the issue date.
  - Deadlines in the next 30 days: courses not closed whose deadline falls between the issue date and 30 days later.
Every item links to the provider's own page (source_url). Nothing is made up: missing values are shown as missing.

Usage:
  python3 scripts/send_newsletter.py [--today YYYY-MM-DD]                 dry run (default): writes out/newsletter-DATE.html/.txt/.json
  python3 scripts/send_newsletter.py --to you@example.com                 one test send, subject starts with [Test]
  python3 scripts/send_newsletter.py --send-to-subscribers --confirm DATE send to every subscriber (deliberate runs only)

Sending needs MAIL_API_KEY (or RESEND_API_KEY / AGENTMAIL_API_KEY for that provider) in the environment (and SUPABASE_SERVICE_ROLE_KEY for --send-to-subscribers).
Nothing schedules this script.
"""
import argparse, ast, datetime, glob, html, json, os, re, string, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "config", "site.json")))
SITE = CFG["base_url"].rstrip("/") + "/"
FUNCTION_URL = CFG["supabase_url"].rstrip("/") + "/functions/v1/" + CFG["subscribe_function"]
# Sender and provider are config values (config/site.json "email"), overridable with MAIL_PROVIDER / MAIL_FROM /
# MAIL_REPLY_TO / MAIL_API_BASE, so changing sender or provider is a config change, not a code change.
EMAIL = CFG["email"]
PROVIDER = os.environ.get("MAIL_PROVIDER") or EMAIL["provider"]
_from = os.environ.get("MAIL_FROM") or f'{EMAIL["from_name"]} <{EMAIL["from_address"]}>'
FROM_HEADER = _from                                                                   # "CoachBadge <hello@coachbadge.com>"
FROM_ADDRESS = (re.search(r"<([^>]+)>", _from) or re.match(r"(.*)", _from)).group(1).strip()  # bare address
REPLY_TO = os.environ.get("MAIL_REPLY_TO") or EMAIL.get("reply_to") or FROM_ADDRESS
DEFAULT_API_BASE = {"resend": "https://api.resend.com", "agentmail": "https://api.agentmail.to/v0"}
API_BASE = (os.environ.get("MAIL_API_BASE") or (EMAIL.get("api_base") if PROVIDER == EMAIL["provider"] else None)
            or DEFAULT_API_BASE.get(PROVIDER, "")).rstrip("/")
KEY_ENV = {"resend": "RESEND_API_KEY", "agentmail": "AGENTMAIL_API_KEY"}
WINDOW_DAYS = 30
TEST_TOKEN = "00000000-0000-0000-0000-000000000000"  # test sends: the link works but matches nobody
CUR = {"GBP": "£", "EUR": "€"}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
e = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def pdate(s):
    try: return datetime.date.fromisoformat(s[:10]) if s and len(s) >= 10 else None
    except ValueError: return None

def fdate(s):
    if not s: return ""
    p = s.split("-")
    if len(p) == 3: return f"{int(p[2])} {MONTHS[int(p[1]) - 1]} {p[0]}"
    if len(p) == 2: return f"{MONTHS[int(p[1]) - 1]} {p[0]}"
    return s

def price_text(c):  # same wording as the site (scripts/build.py)
    p = c.get("price") or {}
    note = p.get("note") or c.get("price_note")
    if p.get("amount") is not None:
        a = p["amount"]; a = int(a) if float(a).is_integer() else a
        sym = CUR.get(p["currency"]); base = f"{sym}{a:,}" if sym else f"{a:,} {p['currency']}"
        return base + (f" ({note})" if note else "")
    return "Not listed" + (f" – {note}" if note else "")

def is_open(c, today):
    d = pdate(c.get("deadline"))
    return c.get("status") == "open" and not (d and d < today)

def latest_report():
    files = sorted(glob.glob(os.path.join(ROOT, "reports", "refresh-*.md")))
    return files[-1] if files else None

def report_changes(path):
    out = {"added": [], "removed": [], "modified": []}
    if not path: return out
    for line in open(path, encoding="utf-8"):
        m = re.match(r"- (added|removed|modified): (\[.*\])\s*$", line)
        if m: out[m.group(1)] = list(ast.literal_eval(m.group(2)))
    return out

def build_issue(today, courses=None, report=None):
    if courses is None:
        courses = json.load(open(os.path.join(ROOT, "data", "courses.json"), encoding="utf-8"))["courses"]
    courses = [c for c in courses if c.get("sport", "football") == "football"]
    rpath = report if report is not None else latest_report()
    ch = report_changes(rpath)
    by_id = {c["id"]: c for c in courses}
    new = [by_id[i] for i in ch["added"] if i in by_id and is_open(by_id[i], today)]
    upd = [by_id[i] for i in ch["modified"] if i in by_id and is_open(by_id[i], today)]
    end = today + datetime.timedelta(days=WINDOW_DAYS)
    due = sorted((c for c in courses if c.get("status") != "closed" and pdate(c.get("deadline")) and today <= pdate(c["deadline"]) <= end),
                 key=lambda c: (c["deadline"], c["id"]))
    return {"issue_date": today.isoformat(), "report": os.path.basename(rpath) if rpath else None,
            "newly_opened": new, "updated_open": upd, "deadlines": due}

def subject_for(issue):
    n, d = len(issue["newly_opened"]), len(issue["deadlines"])
    parts = []
    if n: parts.append(f"{n} newly opened course{'s' if n != 1 else ''}")
    if d: parts.append(f"{d} deadline{'s' if d != 1 else ''} in the next {WINDOW_DAYS} days")
    return "CoachBadge weekly: " + (", ".join(parts) if parts else "no new courses this week")

def _facts(c):
    return [("Provider", c.get("provider")), ("Country", c.get("country")), ("Level", c.get("level")),
            ("Deadline", fdate(c.get("deadline")) or c.get("application_window") or "Not stated"),
            ("Starts", fdate(c.get("start_date")) or "Not stated"), ("Price", price_text(c))]

def _item_html(c):
    facts = " · ".join(f"{k}: {e(v)}" for k, v in _facts(c) if v)
    return (f'<tr><td style="padding:10px 0;border-bottom:1px solid #eef1f4">'
            f'<a href="{e(c["source_url"])}" style="color:#0b5cad;font-weight:700;text-decoration:none">{e(c["title"])}</a>'
            f'<div style="font-size:13px;color:#3d4f5c">{facts}</div>'
            f'<div style="font-size:12px"><a href="{e(c["source_url"])}" style="color:#5b6b78">Provider\'s page</a> · checked {e(fdate(c.get("fetched_at")))}</div></td></tr>')

def _item_text(c):
    facts = "\n".join(f"   {k}: {v}" for k, v in _facts(c) if v)
    return f"- {c['title']}\n{facts}\n   Provider's page: {c['source_url']}\n   Checked: {fdate(c.get('fetched_at'))}"

SECTIONS = [("newly_opened", "Newly opened"), ("updated_open", "Updated open courses"), ("deadlines", f"Deadlines in the next {WINDOW_DAYS} days")]

def resources_parts():
    """Optional 'Resources' line (config newsletter_resources): affiliate links with the same disclosure as the site."""
    res = CFG.get("resources", []) if CFG.get("newsletter_resources") else []
    if not res: return "", ""
    h = ('<p style="margin:16px 0 0;font-size:14px"><strong>Resources:</strong> '
         + " · ".join(f'<a href="{e(x["url"])}" rel="sponsored noopener" style="color:#0b5cad">{e(x["name"])}</a>' for x in res)
         + f' (<a href="{SITE}resources.html" style="color:#0b5cad">what they are</a>)</p>'
         + f'<p style="margin:4px 0 0;font-size:12px;color:#5b6b78">{e(CFG["affiliate_disclosure"])}</p>')
    t = ("Resources: " + " · ".join(f'{x["name"]} {x["url"]}' for x in res) + f"\nWhat they are: {SITE}resources.html\n"
         + CFG["affiliate_disclosure"] + "\n")
    return h, t

def render(issue, unsubscribe_url):
    today = datetime.date.fromisoformat(issue["issue_date"])
    intro_bits = []
    for key, label in SECTIONS:
        if issue[key]: intro_bits.append(f"{label.lower()}: {len(issue[key])}")
    intro = ("This week on CoachBadge, " + "; ".join(intro_bits) + ".") if intro_bits else "No newly opened courses and no deadlines in the next 30 days this week."
    sh, st = [], []
    for key, label in SECTIONS:
        items = issue[key]
        if not items: continue
        sh.append(f'<h2 style="margin:18px 0 4px;font-size:17px">{e(label)}</h2><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
                  + "".join(_item_html(c) for c in items) + "</table>")
        st.append(f"{label.upper()}\n\n" + "\n\n".join(_item_text(c) for c in items))
    vals = {"subject": e(subject_for(issue)), "site": SITE, "issue_date": fdate(today.isoformat()), "intro": e(intro),
            "sections": "\n".join(sh), "unsubscribe_url": e(unsubscribe_url), "disclaimer": e(CFG["disclaimer"]), "resources": resources_parts()[0]}
    tvals = dict(vals, subject=subject_for(issue), intro=intro, sections="\n\n".join(st), unsubscribe_url=unsubscribe_url, disclaimer=CFG["disclaimer"], resources=resources_parts()[1])
    h = string.Template(open(os.path.join(ROOT, "templates", "newsletter.html"), encoding="utf-8").read()).substitute(vals)
    t = string.Template(open(os.path.join(ROOT, "templates", "newsletter.txt"), encoding="utf-8").read()).substitute(tvals)
    return h, t

def unsubscribe_url(token): return f"{SITE}unsubscribe.html?t={urllib.parse.quote(token)}"

def unsubscribe_headers(token):  # RFC 8058 one-click, same as the welcome email
    return {"List-Unsubscribe": f"<{FUNCTION_URL}?unsubscribe={urllib.parse.quote(token)}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}

def message(issue, token, test=False):
    h, t = render(issue, unsubscribe_url(token))
    subj = ("[Test] " if test else "") + subject_for(issue)
    return {"subject": subj, "html": h, "text": t, "headers": unsubscribe_headers(token), "labels": ["coachbadge-weekly"]}

def _http(url, method="GET", headers=None, body=None):
    req = urllib.request.Request(url, method=method, headers=headers or {}, data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read() or b"null")

def agentmail_send(key, to, msg):
    # AgentMail: the inbox id is the sender address (works the same for a custom-domain inbox such as hello@coachbadge.com).
    url = f"{API_BASE}/inboxes/{urllib.parse.quote(FROM_ADDRESS)}/messages/send"
    return _http(url, "POST", {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, dict(msg, to=[to]))

def resend_send(key, to, msg):
    # Resend /emails: one recipient per call; List-Unsubscribe and List-Unsubscribe-Post go in "headers".
    body = {"from": FROM_HEADER, "to": [to], "reply_to": REPLY_TO, "subject": msg["subject"], "html": msg["html"],
            "text": msg["text"], "headers": msg["headers"], "tags": [{"name": "type", "value": (msg.get("labels") or ["coachbadge"])[0]}]}
    return _http(f"{API_BASE}/emails", "POST", {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                               "User-Agent": "CoachBadge-newsletter/1.0"}, body)

SENDERS = {"resend": resend_send, "agentmail": agentmail_send}  # same (key, to, msg) signature

def send(key, to, msg):
    if PROVIDER not in SENDERS: raise SystemExit(f"unknown mail provider {PROVIDER!r}")
    return SENDERS[PROVIDER](key, to, msg)

def subscribers(service_key):
    url = CFG["supabase_url"].rstrip("/") + f"/rest/v1/{CFG['newsletter_table']}?select=email,token&order=id"
    return _http(url, headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"})

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--today", default=datetime.date.today().isoformat())
    ap.add_argument("--out", default=os.path.join(ROOT, "out"))
    ap.add_argument("--to", help="send one test copy to this address")
    ap.add_argument("--send-to-subscribers", action="store_true")
    ap.add_argument("--confirm", help="must equal --today for --send-to-subscribers")
    ap.add_argument("--allow-empty", action="store_true", help="allow sending an issue with nothing in it")
    a = ap.parse_args(argv)
    today = datetime.date.fromisoformat(a.today)
    issue = build_issue(today)
    os.makedirs(a.out, exist_ok=True)
    m = message(issue, TEST_TOKEN, test=bool(a.to))
    base = os.path.join(a.out, f"newsletter-{today.isoformat()}")
    open(base + ".html", "w", encoding="utf-8").write(m["html"])
    open(base + ".txt", "w", encoding="utf-8").write(m["text"])
    json.dump(m, open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"sender {FROM_HEADER} (reply-to {REPLY_TO}) via {PROVIDER}")
    print(f"issue {today}: {len(issue['newly_opened'])} newly opened, {len(issue['updated_open'])} updated, "
          f"{len(issue['deadlines'])} deadlines (report {issue['report']}); wrote {base}.html/.txt/.json")
    if not (a.to or a.send_to_subscribers):
        print("dry run: nothing sent"); return 0
    empty = not (issue["newly_opened"] or issue["updated_open"] or issue["deadlines"])
    if empty and not a.allow_empty:
        print("refusing to send an empty issue (use --allow-empty)", file=sys.stderr); return 2
    kenv = KEY_ENV.get(PROVIDER, "MAIL_API_KEY")
    key = os.environ.get("MAIL_API_KEY") or os.environ.get(kenv)
    if not key: print(f"MAIL_API_KEY / {kenv} is not set", file=sys.stderr); return 2
    if a.to:
        r = send(key, a.to, m); print("test sent to", a.to, (r or {}).get("message_id") or (r or {}).get("id", "")); return 0
    if a.confirm != today.isoformat():
        print(f"--send-to-subscribers needs --confirm {today.isoformat()}", file=sys.stderr); return 2
    sk = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not sk: print("SUPABASE_SERVICE_ROLE_KEY is not set", file=sys.stderr); return 2
    sent = 0
    for s in subscribers(sk):
        try: send(key, s["email"], message(issue, s["token"])); sent += 1
        except Exception as ex: print("failed:", type(ex).__name__, file=sys.stderr)
        time.sleep(1)
    print("sent", sent); return 0

if __name__ == "__main__":
    sys.exit(main())
