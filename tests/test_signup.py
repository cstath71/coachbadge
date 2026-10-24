"""Newsletter form tests. Offline: they check the built HTML and run the form script in Node with a fake DOM and fetch."""
import json, os, re, shutil, subprocess, unittest
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
CFG = json.load(open(os.path.join(ROOT, "config", "site.json")))
TABLE = "coachbadge_subscribers"
EXPECTED_ACTION = f"https://uufmlmwgvoqhhtqgrclu.supabase.co/rest/v1/{TABLE}"
soup = lambda p: BeautifulSoup(open(os.path.join(DIST, p)).read(), "html.parser")
SUB_PAGES = ("index.html", "newsletter.html")

class TestSignupForm(unittest.TestCase):
    def forms(self, p):
        return [f for f in soup(p).select("form.nl") if f.get("data-table") == TABLE]

    def test_config_points_at_table(self):
        self.assertEqual(CFG["newsletter_table"], TABLE)
        self.assertTrue(CFG["supabase_publishable_key"].startswith("sb_publishable_"), "only the public key may be in the site")
        self.assertNotIn("service_role", json.dumps(CFG))

    def test_forms_post_to_right_table(self):
        for p in SUB_PAGES:
            with self.subTest(p):
                fs = self.forms(p); self.assertEqual(len(fs), 1)
                f = fs[0]
                self.assertEqual(f["action"], EXPECTED_ACTION)
                self.assertEqual(f["method"], "post")
                self.assertEqual(f["onsubmit"], "return cbSub(this)")
                em = f.select_one('input[type=email][name=email]')
                self.assertIsNotNone(em); self.assertTrue(em.has_attr("required")); self.assertEqual(em["maxlength"], "254")

    def test_home_form_near_top(self):
        html = open(os.path.join(DIST, "index.html")).read()
        self.assertLess(html.index('id="subscribe-top"'), html.index('class="board"'), "form must come before the course board")

    def test_honeypot_markup(self):
        for p in SUB_PAGES + ("privacy.html",):
            for f in soup(p).select("form.nl"):
                with self.subTest(p):
                    hp = f.select_one('input[name=cb_hp_note]')
                    self.assertIsNotNone(hp)
                    self.assertEqual(hp["tabindex"], "-1"); self.assertEqual(hp["autocomplete"], "off")
                    self.assertEqual(hp["aria-hidden"], "true"); self.assertIn("left:-9999px", hp["style"])

    def test_promise_copy_without_numbers(self):
        for p in SUB_PAGES:
            box = soup(p).select_one(".nl-box").get_text(" ")
            with self.subTest(p):
                self.assertIn("One free short email a week", box)
                self.assertIn("newly opened courses and deadlines coming up", box)
                self.assertIn("unsubscribe link", box)
                self.assertFalse(re.search(r"\d", box), "no numbers or subscriber counts in the promise")

    def test_sticky_bar(self):
        for p in ("index.html", "countries.html", "country/italy.html", "level/uefa-b.html"):
            if not os.path.exists(os.path.join(DIST, p)): continue
            with self.subTest(p):
                bar = soup(p).select_one("#nl-bar"); self.assertIsNotNone(bar)
                self.assertIsNotNone(bar.select_one(".nl-bar-x"))
                self.assertTrue(bar.select_one(".nl-bar-go")["href"].endswith("newsletter.html"))
        css = open(os.path.join(DIST, "style.css")).read()
        self.assertRegex(css, r"\.nl-bar\{position:fixed;[^}]*bottom:0")
        self.assertIsNone(soup("newsletter.html").select_one("#nl-bar"))

    def test_no_storage_or_cookies_in_form_script(self):
        for p in SUB_PAGES:
            js = "".join(s.get_text() for s in soup(p).find_all("script") if "cbSub" in s.get_text() or "nl-bar" in s.get_text())
            with self.subTest(p):
                for bad in ("document.cookie", "localStorage", "sessionStorage", "service_role"): self.assertNotIn(bad, js)

    def test_privacy_wording(self):
        t = re.sub(r"\s+", " ", soup("privacy.html").get_text(" "))
        self.assertIn("only your email address and the time you signed up", t)
        self.assertIn("Why:", t); self.assertIn("How to unsubscribe:", t)
        self.assertIn("every email will include an unsubscribe link", t)
        self.assertNotIn("no newsletter sign-up yet", t)
        for bad in ("PrimeLogic", "Stathopoulos", "Switzerland", "Swiss"): self.assertNotIn(bad.lower(), t.lower())
        uf = soup("privacy.html").select_one("#unsubscribe form")
        self.assertEqual(uf["action"], EXPECTED_ACTION.replace(TABLE, CFG["unsubscribe_table"]))

    def test_readme_notes_no_emails(self):
        r = open(os.path.join(ROOT, "README.md")).read()
        self.assertIn(TABLE, r); self.assertRegex(r, r"(?i)no emails? (are|is) sent")

NODE_HARNESS = r"""
const [src, hpValue, action] = process.argv.slice(1);
const calls = [];
global.window = {}; global.fetch = (url, o) => { calls.push({url, o}); return Promise.resolve({ok: true, status: 201}); };
eval(src);
const msg = {textContent: ''};
const inputs = {email: {value: ' Test+CoachBadge@example.com ', checkValidity: () => true}, hp: {value: hpValue}, btn: {disabled: false}};
const f = {action, reset() {}, getAttribute: () => 'OK-MSG', parentNode: {querySelector: () => msg},
  querySelector: (q) => q.includes('email') ? inputs.email : q.includes('cb_hp_note') ? inputs.hp : inputs.btn};
const ret = window.cbSub(f);
setTimeout(() => console.log(JSON.stringify({ret, calls, msg: msg.textContent})), 20);
"""

@unittest.skipUnless(shutil.which("node"), "node not installed")
class TestSignupScript(unittest.TestCase):
    def run_form(self, hp):
        js = "".join(s.get_text() for s in soup("newsletter.html").find_all("script") if "window.cbSub" in s.get_text())
        self.assertTrue(js)
        out = subprocess.run(["node", "-e", NODE_HARNESS, js, hp, EXPECTED_ACTION], capture_output=True, text=True, timeout=20)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_posts_email_to_table_with_public_key(self):
        r = self.run_form("")
        self.assertFalse(r["ret"]); self.assertEqual(len(r["calls"]), 1)
        c = r["calls"][0]
        self.assertEqual(c["url"], EXPECTED_ACTION); self.assertEqual(c["o"]["method"], "POST")
        self.assertEqual(c["o"]["headers"]["apikey"], CFG["supabase_publishable_key"])
        self.assertEqual(c["o"]["headers"]["Prefer"], "return=minimal")
        self.assertEqual(json.loads(c["o"]["body"]), {"email": "Test+CoachBadge@example.com"}, "sends only the email")
        self.assertEqual(r["msg"], "OK-MSG")

    def test_honeypot_blocks_send(self):
        r = self.run_form("i am a bot")
        self.assertEqual(r["calls"], [], "a filled honeypot must not send anything")
        self.assertEqual(r["msg"], "OK-MSG", "bots still see a normal success message")

class TestMigration(unittest.TestCase):
    def test_insert_only_rls_and_honeypot(self):
        sql = open(os.path.join(ROOT, "supabase", "migrations", "20261024_coachbadge_subscribers.sql")).read()
        self.assertIn(f"create table if not exists public.{TABLE}", sql)
        self.assertIn(f"alter table public.{TABLE} enable row level security", sql)
        self.assertIn(f"revoke all on public.{TABLE} from anon, authenticated", sql)
        self.assertIn(f"grant insert (email, cb_hp_note) on public.{TABLE} to anon", sql)
        self.assertNotRegex(sql, r"(?i)grant (select|update|delete)")
        self.assertNotRegex(sql, r"(?i)for (select|update|delete|all) to anon")
        self.assertIn("if coalesce(btrim(new.cb_hp_note), '') <> '' then return null", sql)
        self.assertIn("char_length(email) between 6 and 254", sql)

if __name__ == "__main__":
    unittest.main()
