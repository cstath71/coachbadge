"""Run: python3 scripts/build.py && python3 -m unittest discover -s tests -v"""
import datetime, glob, json, os, re, sys, unittest
from urllib.parse import urlparse
import yaml
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
DATA = json.load(open(os.path.join(ROOT, "data", "courses.json")))
CFG = json.load(open(os.path.join(ROOT, "config", "site.json")))
STATUSES = {"open", "full", "closed", "upcoming", "unknown"}
FORMATS = {None, "residential", "online", "blended"}
norm = lambda s: re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()
HTML = sorted(glob.glob(os.path.join(DIST, "**", "*.html"), recursive=True))

def iso(s):
    if s is None: return True
    return bool(re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", s))

class TestData(unittest.TestCase):
    def test_required_fields(self):
        ids = set()
        for c in DATA["courses"]:
            with self.subTest(c["id"]):
                self.assertNotIn(c["id"], ids); ids.add(c["id"])
                self.assertEqual(c["sport"], "football", "the site is football-only for now")
                for k in ("country", "provider", "level", "title"): self.assertTrue(c.get(k))
                self.assertTrue(urlparse(c["source_url"]).scheme == "https", c["source_url"])
                datetime.date.fromisoformat(c["fetched_at"])
                self.assertIn(c["status"], STATUSES); self.assertIn(c.get("format"), FORMATS)
                for k in ("deadline", "start_date", "end_date"): self.assertTrue(iso(c.get(k)), (k, c.get(k)))
                self.assertTrue(c.get("evidence"), "every entry needs verbatim evidence")
                self.assertTrue(c.get("status_basis"))
                if c.get("price"): self.assertTrue(c["price"]["currency"] and c["price"]["amount"] > 0)

    def test_open_needs_page_evidence(self):
        cue = re.compile(r"book now|freie plätze|ansök|ansökan|anmäl|apply|öppen|open", re.I)
        for c in DATA["courses"]:
            if c["status"] == "open":
                with self.subTest(c["id"]):
                    self.assertTrue(any(cue.search(x) for x in c["evidence"] + [c["status_basis"]]), c["status_basis"])

    def test_evidence_is_on_cached_page(self):
        from fetch import to_text
        from render import get
        if not os.path.isdir(os.path.join(ROOT, "raw", "cache")):
            self.skipTest("raw/ cache not present (it is not committed)")
        cache = {}
        for c in DATA["courses"]:
            urls = [c["source_url"]] + (c.get("extra_sources") or [])
            for u in urls:
                if u not in cache: cache[u] = norm(to_text(get(u, rendered=bool(c.get("render")))))
            text = " ".join(cache[u] for u in urls)
            for ev in c["evidence"]:
                with self.subTest(c["id"], ev=ev[:40]):
                    self.assertIn(norm(ev), text)

    def test_sources_file(self):
        src = yaml.safe_load(open(os.path.join(ROOT, "data", "sources.yaml")))
        for s in src["football"] + src["basketball"]:
            with self.subTest(s["association"]):
                self.assertIn(s["readable"], {"yes", "no", "partial"})
                self.assertTrue(s["url"].startswith("https://"))
                if s["readable"] == "no": self.assertTrue(s.get("reason"))

class TestSite(unittest.TestCase):
    def test_built(self):
        self.assertTrue(HTML, "run scripts/build.py first")
        for f in ("robots.txt", "sitemap.xml", "llms.txt", "data/courses.json", "index.html", "methodology.html",
                  "about.html", "privacy.html", "terms.html", "newsletter.html"):
            self.assertTrue(os.path.exists(os.path.join(DIST, f)), f)

    def test_banned_words(self):
        banned = re.compile(r"official|mandatory|primelogic|stathopoulos", re.I)
        files = HTML + [os.path.join(DIST, f) for f in ("llms.txt", "robots.txt", "sitemap.xml", "data/courses.json")] + [os.path.join(ROOT, "README.md")]
        for f in files:
            with self.subTest(os.path.relpath(f, ROOT)):
                m = banned.search(open(f).read()); self.assertIsNone(m, m and m.group(0))

    def test_owner_pages_do_not_mention_owner_country(self):
        for f in ("about.html", "privacy.html", "terms.html", "newsletter.html"):
            self.assertNotIn("Switzerland", open(os.path.join(DIST, f)).read())
        self.assertNotIn("Switzerland", open(os.path.join(ROOT, "README.md")).read())

    def test_wordmark_left_and_no_logos(self):
        for f in HTML:
            with self.subTest(os.path.relpath(f, DIST)):
                soup = BeautifulSoup(open(f).read(), "html.parser")
                wrap = soup.select_one("header.top .wrap")
                kids = [k for k in wrap.children if getattr(k, "name", None)]
                self.assertEqual(kids[0].get("id"), "wordmark", "wordmark must be first (left) in the header")
                self.assertEqual(kids[0].get_text(), CFG["wordmark"])
                self.assertEqual(kids[1].name, "nav")
                self.assertEqual(soup.find_all("img"), [], "no logo images")
                self.assertIn(CFG["disclaimer"], soup.get_text())
                self.assertIn(CFG["brand"], soup.title.get_text())
        css = open(os.path.join(DIST, "style.css")).read()
        self.assertNotRegex(css, r"\.brand\{[^}]*(order:[1-9]|margin-left:auto|float:right)")
        self.assertNotRegex(css, r"flex-direction:row-reverse")

    def test_internal_links(self):
        for f in HTML:
            soup = BeautifulSoup(open(f).read(), "html.parser")
            for a in soup.select("[href]"):
                h = a["href"]
                if h.startswith(("http", "mailto:", "#")): continue
                with self.subTest(os.path.relpath(f, DIST), href=h):
                    self.assertTrue(os.path.exists(os.path.normpath(os.path.join(os.path.dirname(f), h.split("#")[0]))))

    def test_external_links(self):
        base = CFG["base_url"]
        for f in HTML:
            for a in BeautifulSoup(open(f).read(), "html.parser").select("a[href^=http]"):
                h = a["href"]
                with self.subTest(href=h):
                    self.assertTrue(h.startswith("https://"))
                    if h.startswith(base): self.assertTrue(os.path.exists(os.path.join(DIST, h[len(base):] or "index.html")))
        if os.path.isdir(os.path.join(ROOT, "raw", "cache")):
            from fetch import fetch
            for c in DATA["courses"]:
                with self.subTest(c["source_url"]):
                    self.assertEqual(fetch(c["source_url"]).get("status"), 200)

    def test_sitemap_and_jsonld(self):
        sm = open(os.path.join(DIST, "sitemap.xml")).read()
        for loc in re.findall(r"<loc>(.*?)</loc>", sm):
            self.assertTrue(os.path.exists(os.path.join(DIST, loc[len(CFG["base_url"]):] or "index.html")), loc)
        for f in HTML:
            for s in BeautifulSoup(open(f).read(), "html.parser").select('script[type="application/ld+json"]'):
                json.loads(s.string)

    def test_counter_inert(self):
        h = open(os.path.join(DIST, "index.html")).read()
        self.assertIn('var E="";if(!E)return;', h) if not CFG["counter_endpoint"] else None
        for k in ("doNotTrack", "globalPrivacyControl", "webdriver", "location.hostname"): self.assertIn(k, h)
        self.assertNotRegex(h, r"document\.cookie|localStorage|sessionStorage")

    def test_open_board_only_open(self):
        soup = BeautifulSoup(open(os.path.join(DIST, "index.html")).read(), "html.parser")
        for t in soup.select(".board .card .tag"):
            self.assertIn(t.get_text(), {"Open", "Closing soon"})

if __name__ == "__main__":
    unittest.main()
