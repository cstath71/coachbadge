"""Affiliate 'Coaching resources' tests: links present, rel sponsored, disclosure next to them and on about/privacy, newsletter line. Offline."""
import glob, json, os, re, sys, unittest
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
CFG = json.load(open(os.path.join(ROOT, "config", "site.json")))
DISCLOSURE = "Some links are affiliate links: if you buy through them, CoachBadge may earn a commission at no extra cost to you."
EXPECTED = {"FootballGPT": "https://footballgpt.co?ref=coach-6174eb", "SoccerTutor.com": "https://soccertutor.com/coach",
            "CoachThem": "https://coachthem.com/?via=coach-badge", "CoachTube": "https://coachtube.com?a=48474dde3a2f471aa7990004b"}
URLS = set(EXPECTED.values())
soup = lambda p: BeautifulSoup(open(os.path.join(DIST, p)).read(), "html.parser")
text = lambda s: re.sub(r"\s+", " ", s.get_text(" ")).strip()
COURSE_PAGES = ["index.html"] + [os.path.relpath(p, DIST) for p in glob.glob(os.path.join(DIST, "country", "*.html")) + glob.glob(os.path.join(DIST, "level", "*.html"))]

class TestResources(unittest.TestCase):
    def test_config(self):
        self.assertEqual(CFG["affiliate_disclosure"], DISCLOSURE)
        self.assertEqual({r["name"]: r["url"] for r in CFG["resources"]}, EXPECTED)
        self.assertIn("a=48474dde3a2f471aa7990004b", EXPECTED["CoachTube"])
        for r in CFG["resources"]:
            self.assertNotRegex(r["desc"], r"\d|%|official|mandatory", "no numbers or claims in descriptions")

    def check_links(self, s, where):
        links = [a for a in s.find_all("a") if a.get("href") in URLS]
        self.assertEqual({a["href"] for a in links}, URLS, where)
        for a in links:
            self.assertEqual(set(a.get("rel") or []), {"sponsored", "noopener"}, f"{where}: {a['href']}")
        return links

    def test_resources_page(self):
        s = soup("resources.html")
        self.assertEqual(s.find("h1").get_text(strip=True), "Coaching resources")
        self.check_links(s, "resources.html")
        self.assertIn(DISCLOSURE, text(s))
        self.assertIn("https://coachbadge.com/resources.html", open(os.path.join(DIST, "sitemap.xml")).read())
        self.assertNotRegex(text(s.find("main")), r"\d+ ?%|commission rate|recurring")

    def test_course_pages_have_labelled_block_with_disclosure(self):
        self.assertGreater(len(COURSE_PAGES), 3)
        for p in COURSE_PAGES:
            with self.subTest(p):
                box = soup(p).select_one("aside.resources")
                self.assertIsNotNone(box)
                self.assertIn("Coaching resources", box.find("h2").get_text())
                self.check_links(box, p)
                self.assertIn(DISCLOSURE, text(box))
                self.assertIsNotNone(box.find("a", href=re.compile(r"resources\.html$")))

    def test_affiliate_links_only_with_disclosure(self):
        for f in glob.glob(os.path.join(DIST, "**", "*.html"), recursive=True):
            s = BeautifulSoup(open(f).read(), "html.parser")
            if any(a.get("href") in URLS for a in s.find_all("a")):
                with self.subTest(os.path.relpath(f, DIST)):
                    self.assertIn(DISCLOSURE, text(s))
                    for a in s.find_all("a", href=lambda h: h in URLS):
                        self.assertIn("sponsored", a.get("rel") or [])

    def test_footer_links_resources_and_privacy_about_disclose(self):
        self.assertIsNotNone(soup("index.html").select_one('footer a[href="resources.html"]'))
        for p in ("privacy.html", "about.html"):
            self.assertIn(DISCLOSURE, text(soup(p)), p)

    def test_course_data_untouched(self):
        data = open(os.path.join(DIST, "data", "courses.json")).read()
        for u in URLS: self.assertNotIn(u, data)

    def test_newsletter_resources_line(self):
        import send_newsletter as nl
        h, t = nl.render(nl.build_issue(__import__("datetime").date(2026, 10, 26)), "https://coachbadge.com/unsubscribe.html?t=x")
        s = BeautifulSoup(h, "html.parser")
        self.assertIn("Resources:", text(s))
        self.check_links(s, "newsletter html")
        self.assertIn(DISCLOSURE, text(s))
        self.assertIn("Resources: ", t); self.assertIn(DISCLOSURE, t)
        for u in URLS: self.assertIn(u, t)
        old = nl.CFG.get("newsletter_resources")
        try:
            nl.CFG["newsletter_resources"] = False
            h2, t2 = nl.render(nl.build_issue(__import__("datetime").date(2026, 10, 26)), "https://coachbadge.com/unsubscribe.html?t=x")
            self.assertNotIn(DISCLOSURE, h2); self.assertNotIn("Resources:", t2)
        finally:
            nl.CFG["newsletter_resources"] = old

if __name__ == "__main__":
    unittest.main()
