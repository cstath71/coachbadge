"""Email tests: welcome template (Node), Edge Function source, weekly newsletter, unsubscribe page. Offline; nothing is sent."""
import datetime, io, json, os, re, shutil, subprocess, sys, tempfile, unittest, contextlib
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
FN_DIR = os.path.join(ROOT, "supabase", "functions", "coachbadge-subscribe")
FUNCTION_URL = "https://uufmlmwgvoqhhtqgrclu.supabase.co/functions/v1/coachbadge-subscribe"
SITE = "https://cstath71.github.io/coachbadge/"
TOKEN = "3f2a1b4c-5d6e-4f70-8a9b-0c1d2e3f4a5b"
BANNED = ("official", "mandatory", "primelogic", "stathopoulos", "switzerland", "swiss", "basketball",
          "shopbotindex", "fusionupdates")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import send_newsletter as nl

def check_copy(tc, text):
    low = text.lower()
    for bad in BANNED: tc.assertNotIn(bad, low, bad)

def check_logo_left(tc, html):
    s = BeautifulSoup(html, "html.parser")
    img = s.find("img", src=SITE + "email-logo.png"); tc.assertIsNotNone(img)
    td = img.find_parent("td"); tc.assertEqual(td.get("align"), "left"); tc.assertIn("text-align:left", td.get("style", ""))
    tc.assertNotIn(".svg", html, "Gmail does not show SVG")
    tc.assertIn("Coach", td.get_text()); tc.assertIn("Badge", td.get_text())

@unittest.skipUnless(shutil.which("node"), "node not installed")
class TestWelcomeEmail(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        js = ("import(process.argv[1]).then(m=>console.log(JSON.stringify({w:m.welcomeEmail(process.argv[2]),from:m.FROM_ADDRESS,"
              "u:m.unsubscribeUrl(process.argv[2]),fn:m.FUNCTION_URL})))")
        out = subprocess.run(["node", "-e", js, os.path.join(FN_DIR, "email.mjs"), TOKEN], capture_output=True, text=True, timeout=20)
        assert out.returncode == 0, out.stderr
        cls.r = json.loads(out.stdout); cls.w = cls.r["w"]

    def test_sender_and_subject(self):
        self.assertEqual(self.r["from"], "coachbadge@agentmail.to")
        self.assertEqual(self.r["fn"], FUNCTION_URL)
        self.assertEqual(self.w["subject"], "Welcome to CoachBadge")

    def test_short_copy_text_and_html(self):
        for part in (self.w["text"], BeautifulSoup(self.w["html"], "html.parser").get_text(" ")):
            t = re.sub(r"\s+", " ", part)
            self.assertIn("Thanks for signing up", t)
            self.assertIn("one short email a week with newly opened football coaching courses and deadlines coming up", t)
            self.assertIn("Independent; not affiliated with UEFA or any association listed.", t)
            check_copy(self, t)
        self.assertLess(len(self.w["text"].split()), 120, "keep it short")

    def test_unsubscribe_link_and_headers(self):
        u = f"{SITE}unsubscribe.html?t={TOKEN}"
        self.assertEqual(self.r["u"], u)
        self.assertIn(u, self.w["text"]); self.assertIn(f'href="{u}"', self.w["html"])
        self.assertEqual(self.w["headers"], {"List-Unsubscribe": f"<{FUNCTION_URL}?unsubscribe={TOKEN}>",
                                             "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"})

    def test_logo_left(self):
        check_logo_left(self, self.w["html"])

    def test_links_follow_settings(self):
        js = ("import(process.argv[1]).then(m=>console.log(JSON.stringify(m.welcomeEmail('t1',{site:'https://coachbadge.com/',"
              "functionUrl:'https://fn.example/x'}))))")
        w = json.loads(subprocess.run(["node", "-e", js, os.path.join(FN_DIR, "email.mjs")], capture_output=True, text=True, timeout=20).stdout)
        self.assertIn("https://coachbadge.com/unsubscribe.html?t=t1", w["text"])
        self.assertIn('src="https://coachbadge.com/email-logo.png"', w["html"])
        self.assertEqual(w["headers"]["List-Unsubscribe"], "<https://fn.example/x?unsubscribe=t1>")

class TestEdgeFunctionSource(unittest.TestCase):
    src = open(os.path.join(FN_DIR, "index.ts")).read()

    def test_honeypot_dedupe_rate_limit(self):
        self.assertIn("body.cb_hp_note", self.src)
        self.assertIn("MAX_PER_IP_PER_HOUR = 5", self.src); self.assertIn("coachbadge_signup_attempts", self.src)
        self.assertIn("MAX_WELCOMES_PER_HOUR", self.src)
        self.assertIn("rows && rows.length", self.src, "a duplicate (no row back) gets no welcome")
        self.assertIn("status: s", self.src); self.assertIn("429", self.src)

    def test_sends_via_agentmail_from_coachbadge_inbox_only(self):
        self.assertIn('"https://api.agentmail.to/v0"', self.src)
        self.assertIn("/inboxes/${encodeURIComponent(MAIL_FROM)}/messages/send", self.src)
        self.assertIn('import { FROM_ADDRESS, FUNCTION_URL, SITE, welcomeEmail } from "./email.mjs"', self.src)
        self.assertIn("headers: m.headers", self.src)

    def test_sender_and_provider_are_settings_and_welcome_off_by_default(self):
        for k in ("MAIL_PROVIDER", "MAIL_FROM", "MAIL_API_BASE", "MAIL_API_KEY", "SITE_URL", "PUBLIC_FUNCTION_URL"):
            self.assertIn(f'env("{k}")', self.src)
        self.assertIn('const WELCOME_ENABLED = env("WELCOME_ENABLED") === "true"', self.src)
        self.assertIn("if (created && WELCOME_ENABLED", self.src)
        check_copy(self, self.src)
        self.assertNotIn("resend", self.src.lower())

    def test_no_secrets_in_source(self):
        for f in os.listdir(FN_DIR):
            t = open(os.path.join(FN_DIR, f)).read()
            self.assertNotRegex(t, r"\bam_[A-Za-z0-9]{10,}|sb_secret_|eyJhbGci", f)
        self.assertIn('env("AGENTMAIL_API_KEY")', self.src); self.assertIn('rpc("coachbadge_mail_config")', self.src)

    def test_unsubscribe_paths(self):
        self.assertIn('searchParams.get("unsubscribe")', self.src, "RFC 8058 one-click POST")
        self.assertIn('body.action === "unsubscribe"', self.src)
        self.assertIn('rpc("coachbadge_unsubscribe"', self.src); self.assertIn("UUID_RE.test(t)", self.src)

    def test_cors_allows_site_only(self):
        self.assertIn('"https://cstath71.github.io"', self.src); self.assertIn('"https://coachbadge.com"', self.src)
        self.assertIn("origin && !ALLOWED.includes(origin)", self.src)

FIXTURE = [
    {"id": "a-new", "sport": "football", "country": "Norway", "provider": "Provider A", "level": "UEFA C", "title": "New C course",
     "price": {"amount": 100, "currency": "EUR"}, "deadline": "2026-12-31", "start_date": "2027-01-10", "status": "open",
     "source_url": "https://p1.example/c", "fetched_at": "2026-10-24"},
    {"id": "b-soon", "sport": "football", "country": "Sweden", "provider": "Provider B", "level": "UEFA B", "title": "Soon B course",
     "price": None, "deadline": "2026-11-10", "status": "open", "source_url": "https://p2.example/b", "fetched_at": "2026-10-24"},
    {"id": "c-closed", "sport": "football", "country": "Spain", "provider": "Provider C", "level": "UEFA A", "title": "Closed A course",
     "price": None, "deadline": "2026-11-05", "status": "closed", "source_url": "https://p3.example/a", "fetched_at": "2026-10-24"},
    {"id": "d-far", "sport": "football", "country": "Italy", "provider": "Provider D", "level": "UEFA Pro", "title": "Far Pro course",
     "price": None, "deadline": "2027-03-01", "status": "open", "source_url": "https://p4.example/p", "fetched_at": "2026-10-24"},
    {"id": "e-past", "sport": "football", "country": "Malta", "provider": "Provider E", "level": "UEFA C", "title": "Past course",
     "price": None, "deadline": "2026-10-01", "status": "open", "source_url": "https://p5.example/c", "fetched_at": "2026-10-24"},
]

class TestNewsletter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp)
        self.report = os.path.join(self.tmp, "refresh-2026-10-24.md")
        open(self.report, "w").write("# Refresh\n\n## Course candidates\n\n- added: ['a-new', 'e-past', 'zz-missing']\n- removed: []\n- modified: ['d-far', 'c-closed']\n")
        self.issue = nl.build_issue(datetime.date(2026, 10, 24), courses=FIXTURE, report=self.report)

    def test_sections_only_from_data(self):
        ids = lambda k: [c["id"] for c in self.issue[k]]
        self.assertEqual(ids("newly_opened"), ["a-new"], "added + open on the issue date; unknown ids dropped")
        self.assertEqual(ids("updated_open"), ["d-far"], "modified + open")
        self.assertEqual(ids("deadlines"), ["b-soon"], "not closed, deadline within 30 days")

    def test_render_text_and_html(self):
        m = nl.message(self.issue, TOKEN)
        self.assertEqual(m["subject"], "CoachBadge weekly: 1 newly opened course, 1 deadline in the next 30 days")
        for c in self.issue["newly_opened"] + self.issue["updated_open"] + self.issue["deadlines"]:
            self.assertIn(c["source_url"], m["text"]); self.assertIn(f'href="{c["source_url"]}"', m["html"])
        self.assertIn("€100", m["text"]); self.assertIn("Not listed", m["text"]); self.assertIn("10 Nov 2026", m["text"])
        self.assertNotIn("Closed A course", m["text"]); self.assertNotIn("Past course", m["text"])
        # every number in the text comes from the data, the date or the fixed 30-day window
        allowed = {"1", "24", "2026", "31", "12", "2027", "10", "30", "100", "0000", "00000000"} | set(TOKEN.replace("-", " ").split())
        for n in re.findall(r"\d+", re.sub(r"https?://\S+", "", m["text"])): self.assertIn(n, allowed, n)
        check_copy(self, m["text"]); check_copy(self, m["html"]); check_logo_left(self, m["html"])
        self.assertIn("Independent; not affiliated with UEFA or any association listed.", m["text"])

    def test_unsubscribe_link_and_headers(self):
        m = nl.message(self.issue, TOKEN)
        u = f"{SITE}unsubscribe.html?t={TOKEN}"
        self.assertIn(u, m["text"]); self.assertIn(f'href="{u}"', m["html"])
        self.assertEqual(m["headers"]["List-Unsubscribe"], f"<{FUNCTION_URL}?unsubscribe={TOKEN}>")
        self.assertEqual(m["headers"]["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    def test_test_send_subject_and_token(self):
        m = nl.message(self.issue, nl.TEST_TOKEN, test=True)
        self.assertTrue(m["subject"].startswith("[Test] "))
        self.assertIn("00000000-0000-0000-0000-000000000000", m["text"])

    def test_dry_run_writes_files_and_sends_nothing(self):
        out = os.path.join(self.tmp, "out")
        called = []
        orig = nl.send; nl.send = lambda *a: called.append(a)
        try:
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                rc = nl.main(["--today", "2026-10-24", "--out", out])
        finally: nl.send = orig
        self.assertEqual(rc, 0); self.assertEqual(called, []); self.assertIn("dry run: nothing sent", buf.getvalue())
        for ext in ("html", "txt", "json"): self.assertTrue(os.path.exists(os.path.join(out, f"newsletter-2026-10-24.{ext}")))

    def test_subscriber_send_needs_confirm_and_keys(self):
        out = os.path.join(self.tmp, "out"); env = dict(os.environ)
        for k in ("AGENTMAIL_API_KEY", "MAIL_API_KEY", "SUPABASE_SERVICE_ROLE_KEY"): os.environ.pop(k, None)
        orig_b = nl.build_issue; nl.build_issue = lambda today: self.issue
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(nl.main(["--today", "2026-10-24", "--out", out, "--send-to-subscribers"]), 2)
                self.assertIn("AGENTMAIL_API_KEY", err.getvalue())
                os.environ["AGENTMAIL_API_KEY"] = "dummy"
                self.assertEqual(nl.main(["--today", "2026-10-24", "--out", out, "--send-to-subscribers", "--confirm", "2026-10-23"]), 2)
                self.assertIn("--confirm 2026-10-24", err.getvalue())
        finally:
            nl.build_issue = orig_b; os.environ.clear(); os.environ.update(env)

    def test_refuses_empty_issue(self):
        empty = {"issue_date": "2026-10-24", "report": None, "newly_opened": [], "updated_open": [], "deadlines": []}
        orig_b = nl.build_issue; nl.build_issue = lambda today: empty
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(nl.main(["--today", "2026-10-24", "--out", os.path.join(self.tmp, "o"), "--to", "x@example.com"]), 2)
            self.assertIn("empty issue", err.getvalue())
        finally: nl.build_issue = orig_b

    def test_sender_is_config(self):
        self.assertEqual((nl.PROVIDER, nl.FROM_ADDRESS), ("agentmail", "coachbadge@agentmail.to"))
        self.assertIn("agentmail", nl.SENDERS)
        src = open(os.path.join(ROOT, "scripts", "send_newsletter.py")).read()
        self.assertNotIn('"coachbadge@agentmail.to"', src, "sender address only in config/site.json")

    def test_not_scheduled(self):
        wf = os.path.join(ROOT, ".github", "workflows")
        for f in os.listdir(wf) if os.path.isdir(wf) else []:
            self.assertNotIn("send_newsletter", open(os.path.join(wf, f)).read(), f)

UNSUB_HARNESS = r"""
const [src, search] = process.argv.slice(1);
const calls = []; const msg = {textContent: ''};
global.document = {getElementById: () => msg}; global.location = {search};
global.fetch = (url, o) => { calls.push({url, o}); return Promise.resolve({ok: true, json: () => Promise.resolve({ok: true, removed: true})}); };
eval(src);
setTimeout(() => console.log(JSON.stringify({calls, msg: msg.textContent})), 30);
"""

class TestUnsubscribePage(unittest.TestCase):
    html = open(os.path.join(DIST, "unsubscribe.html")).read()

    def test_noindex_and_not_in_sitemap(self):
        s = BeautifulSoup(self.html, "html.parser")
        self.assertEqual(s.find("meta", attrs={"name": "robots"})["content"], "noindex,nofollow")
        self.assertNotIn("unsubscribe.html", open(os.path.join(DIST, "sitemap.xml")).read())
        self.assertIsNone(s.select_one("#nl-bar")); self.assertIsNone(s.select_one("form"))

    def test_email_logo_png_shipped(self):
        b = open(os.path.join(DIST, "email-logo.png"), "rb").read(8); self.assertEqual(b, b"\x89PNG\r\n\x1a\n")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_posts_token_once_on_load(self):
        js = "".join(t.get_text() for t in BeautifulSoup(self.html, "html.parser").find_all("script") if "unsub-msg" in t.get_text())
        r = json.loads(subprocess.run(["node", "-e", UNSUB_HARNESS, js, f"?t={TOKEN}"], capture_output=True, text=True, timeout=20).stdout)
        self.assertEqual(len(r["calls"]), 1)
        self.assertEqual(r["calls"][0]["url"], FUNCTION_URL)
        self.assertEqual(json.loads(r["calls"][0]["o"]["body"]), {"action": "unsubscribe", "token": TOKEN})
        self.assertIn("deleted", r["msg"])
        r = json.loads(subprocess.run(["node", "-e", UNSUB_HARNESS, js, "?t=nope"], capture_output=True, text=True, timeout=20).stdout)
        self.assertEqual(r["calls"], []); self.assertIn("incomplete", r["msg"])

if __name__ == "__main__":
    unittest.main()
