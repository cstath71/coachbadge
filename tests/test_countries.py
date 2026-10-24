"""Empty-country UX, the headless render helper and the Austria data added on 24 Oct 2026."""
import glob, json, os, re, sys, unittest
from unittest import mock
import yaml
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
DATA = json.load(open(os.path.join(ROOT, "data", "courses.json")))
SOURCES = [s for s in yaml.safe_load(open(os.path.join(ROOT, "data", "sources.yaml")))["football"] if s.get("enabled", True)]
COUNTRIES_WITH = {c["country"] for c in DATA["courses"]}
EMPTY = sorted({s["country"] for s in SOURCES} - COUNTRIES_WITH)
ZERO = re.compile(r"\b0\s+(open|courses?|tracked)\b|\bnone of the 0\b|\(0 open|\b0 of\b", re.I)

def soup(rel):
    with open(os.path.join(DIST, rel)) as f: return BeautifulSoup(f.read(), "html.parser")
def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

class TestEmptyCountries(unittest.TestCase):
    def test_there_are_empty_countries_to_check(self):
        self.assertTrue(EMPTY, "expected at least one country without courses")
        self.assertNotIn("Austria", EMPTY)

    def test_empty_country_page_has_empty_state_with_links_and_reason(self):
        for ct in EMPTY:
            with self.subTest(ct=ct):
                s = soup(f"country/{slug(ct)}.html")
                box = s.find(id="no-open-courses")
                self.assertIsNotNone(box, ct)
                self.assertIn("No open courses right now", box.get_text())
                self.assertIn("Why:", box.get_text())
                hrefs = {a["href"] for a in box.find_all("a")}
                want = {x["url"] for x in SOURCES if x["country"] == ct}
                self.assertEqual(hrefs, want)
                self.assertIn("the association's course pages", box.get_text())

    def test_no_zero_wording_in_summary_faq_or_jsonld(self):
        for ct in EMPTY:
            with self.subTest(ct=ct):
                s = soup(f"country/{slug(ct)}.html")
                self.assertIsNone(ZERO.search(s.find(id="summary").get_text()))
                for tag in s.find_all("script", type="application/ld+json"):
                    self.assertIsNone(ZERO.search(tag.get_text()), tag.get_text()[:200])
                    for item in (lambda d: d if isinstance(d, list) else [d])(json.loads(tag.get_text())):
                        self.assertNotEqual(item.get("@type"), "ItemList")
                self.assertIsNone(ZERO.search(s.get_text(" ")))
                desc = s.find("meta", attrs={"name": "description"})["content"]
                self.assertIsNone(ZERO.search(desc))

    def test_listings_say_check_association(self):
        items = {a.get_text(" ", strip=True) for a in soup("countries.html").select("ul.pill-list a")}
        for ct in EMPTY:
            self.assertIn(f"{ct} (Check association)", items)
        for f in ["index.html", "countries.html", "levels.html"]:
            self.assertIsNone(ZERO.search(soup(f).get_text(" ")), f)
        with open(os.path.join(DIST, "llms.txt")) as f: llms = f.read()
        self.assertIsNone(ZERO.search(llms))
        self.assertIn("Check association", llms)

    def test_country_with_open_courses_has_no_empty_state(self):
        self.assertIsNone(soup("country/austria.html").find(id="no-open-courses"))

class TestAustria(unittest.TestCase):
    def test_austria_courses(self):
        at = [c for c in DATA["courses"] if c["country"] == "Austria"]
        self.assertEqual(len(at), 15)
        self.assertEqual({c["level"] for c in at}, {"UEFA C", "UEFA B"})
        for c in at:
            self.assertTrue(c["source_url"].startswith("https://"))
            self.assertTrue(c.get("evidence"), c["id"])

    def test_render_flag_only_on_js_sources(self):
        flagged = {c["source_url"] for c in DATA["courses"] if c.get("render")}
        self.assertTrue(flagged)
        self.assertTrue(all(re.search(r"kfv-fussball\.at|tfv\.at", u) for u in flagged), flagged)

class TestSourcesFile(unittest.TestCase):
    def test_empty_countries_have_reason_and_date(self):
        for ct in EMPTY:
            for x in [s for s in SOURCES if s["country"] == ct]:
                with self.subTest(ct=ct, url=x["url"]):
                    self.assertEqual(x["checked"], "2026-10-24")
                    self.assertTrue(x.get("reason") or x.get("note"))
                    self.assertNotRegex((x.get("reason") or x.get("note")).lower(), r"official|linkedin")

class TestRenderHelper(unittest.TestCase):
    def test_iri_encodes_non_ascii_only(self):
        from fetch import iri
        self.assertEqual(iri("https://www.ofv.at/ofv/OÖFV.pdf?ch=1"), "https://www.ofv.at/ofv/O%C3%96FV.pdf?ch=1")
        self.assertEqual(iri("https://a.b/x%CC%88y?q=1&r=2"), "https://a.b/x%CC%88y?q=1&r=2")

    def test_challenge_detection(self):
        from render import is_challenge
        self.assertTrue(is_challenge("<html><title>Just a moment...</title></html>"))
        self.assertTrue(is_challenge("<html><head><title>x</title></head><body><div id=cf-challenge></div></body></html>"))
        self.assertTrue(is_challenge("<html><title>x</title><body>captcha</body></html>"))
        big = "<html><title>Courses</title><body>" + "<p>UEFA C course dates and prices.</p>" * 40 + '<script src="https://www.google.com/recaptcha/api.js"></script><div class="g-recaptcha"></div></body></html>'
        self.assertFalse(is_challenge(big))

    def test_render_respects_robots_without_launching_a_browser(self):
        import render
        with mock.patch.object(render, "robots_ok", return_value=False), \
             mock.patch.object(render, "CACHE", os.path.join(ROOT, "raw", "cache-test")), \
             mock.patch.dict(sys.modules, {"playwright": None, "playwright.sync_api": None}):
            m = render.render("https://example.invalid/blocked", refresh=True)
        self.assertEqual(m["error"], "disallowed by robots.txt")
        self.assertEqual(m["body"], b"")

    def test_get_dispatches_on_render_flag(self):
        import render
        with mock.patch.object(render, "render", return_value={"r": 1}) as r, mock.patch("fetch.fetch", return_value={"f": 1}) as f:
            self.assertEqual(render.get("https://x.y/", rendered=True), {"r": 1})
            self.assertEqual(render.get("https://x.y/"), {"f": 1})
        r.assert_called_once(); f.assert_called_once()

if __name__ == "__main__":
    unittest.main()
