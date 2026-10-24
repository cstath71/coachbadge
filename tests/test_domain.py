import json, os, re, subprocess, sys, unittest
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
CFG = json.load(open(os.path.join(ROOT, "config", "site.json")))
DOMAIN = "coachbadge.com"
BASE = f"https://{DOMAIN}/"


class CustomDomain(unittest.TestCase):
    def test_cname_file(self):
        self.assertEqual(open(os.path.join(ROOT, "CNAME")).read().strip(), DOMAIN)
        self.assertEqual(open(os.path.join(DIST, "CNAME")).read().strip(), DOMAIN)

    def test_config_uses_custom_domain(self):
        self.assertEqual(CFG["domain"], DOMAIN)
        self.assertEqual(CFG["base_url"], BASE)

    def test_canonical_and_og_urls(self):
        for dp, _, fs in os.walk(DIST):
            for f in fs:
                if not f.endswith(".html"): continue
                soup = BeautifulSoup(open(os.path.join(dp, f)).read(), "html.parser")
                with self.subTest(f):
                    can = soup.select_one('link[rel="canonical"]')["href"]
                    self.assertTrue(can.startswith(BASE), can)
                    og = soup.select_one('meta[property="og:url"]')["content"]
                    self.assertEqual(og, can)

    def test_robots_sitemap_llms(self):
        self.assertIn(f"Sitemap: {BASE}sitemap.xml", open(os.path.join(DIST, "robots.txt")).read())
        locs = re.findall(r"<loc>(.*?)</loc>", open(os.path.join(DIST, "sitemap.xml")).read())
        self.assertTrue(locs)
        for loc in locs: self.assertTrue(loc.startswith(BASE), loc)
        self.assertIn(f"({BASE})", open(os.path.join(DIST, "llms.txt")).read())

    def test_no_github_io_urls_left(self):
        for dp, _, fs in os.walk(DIST):
            for f in fs:
                if f.endswith((".html", ".txt", ".xml", ".json")):
                    with self.subTest(f):
                        self.assertNotIn("cstath71.github.io", open(os.path.join(dp, f)).read())


if __name__ == "__main__":
    unittest.main()
