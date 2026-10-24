"""CoachBadge is football-only for now: basketball sources stay in sources.yaml, switched off (enabled: false)."""
import glob, json, os, re, sys, unittest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
OFF = re.compile(r"basketball|baloncesto|pallacanestro|\bfiba\b|\bfecc\b", re.I)

class TestFootballOnly(unittest.TestCase):
    def test_no_page_llms_or_sitemap_mentions_basketball(self):
        files = sorted(glob.glob(os.path.join(DIST, "**", "*.html"), recursive=True))
        self.assertTrue(files, "run scripts/build.py first")
        files += [os.path.join(DIST, f) for f in ("llms.txt", "sitemap.xml", "robots.txt", "data/courses.json")]
        files += [os.path.join(ROOT, "README.md"), os.path.join(ROOT, "config", "site.json")]
        for f in files:
            with self.subTest(os.path.relpath(f, ROOT)):
                m = OFF.search(open(f).read()); self.assertIsNone(m, m and m.group(0))

    def test_sitemap_has_no_removed_pages(self):
        locs = re.findall(r"<loc>([^<]+)</loc>", open(os.path.join(DIST, "sitemap.xml")).read())
        for u in locs:
            base = json.load(open(os.path.join(ROOT, "config", "site.json")))["base_url"]
            path = u[len(base):] or "index.html"
            with self.subTest(u): self.assertTrue(os.path.exists(os.path.join(DIST, path)), "sitemap entry without a page")
        for gone in ("country/europe-fiba-europe.html", "country/serbia.html", "country/lithuania.html", "country/turkiye.html"):
            self.assertFalse(os.path.exists(os.path.join(DIST, gone)), gone)
        self.assertFalse(glob.glob(os.path.join(DIST, "level", "basketball-*.html")))

    def test_country_pages_only_with_football(self):
        src = yaml.safe_load(open(os.path.join(ROOT, "data", "sources.yaml")))
        courses = json.load(open(os.path.join(ROOT, "data", "courses.json")))["courses"]
        football = {s["country"] for s in src["football"]} | {c["country"] for c in courses}
        for f in glob.glob(os.path.join(DIST, "country", "*.html")):
            with self.subTest(os.path.basename(f)):
                h1 = re.search(r"<h1>(?:Football c|C)oaching courses in ([^<]+)</h1>", open(f).read()).group(1)
                self.assertIn(h1.replace("&amp;", "&"), football)

    def test_no_sport_filter_with_one_sport(self):
        self.assertNotIn('data-f="sport"', open(os.path.join(DIST, "index.html")).read())

    def test_basketball_sources_kept_but_disabled(self):
        src = yaml.safe_load(open(os.path.join(ROOT, "data", "sources.yaml")))
        self.assertTrue(src.get("basketball"), "basketball sources must stay in the file so they can come back")
        for s in src["basketball"]:
            with self.subTest(s["association"]): self.assertIs(s.get("enabled"), False)
        for s in src["football"]:
            self.assertNotEqual(s.get("enabled"), False, s["association"])

    def test_scripts_skip_disabled_sources(self):
        import sources
        self.assertEqual(sources.enabled_sports(), {"football"})
        on = {s["url"] for lst in sources.enabled().values() for s in lst}
        bb = {s["url"] for s in sources.load_all()["basketball"]}
        self.assertFalse(on & bb)
        # synthetic check of the rule itself
        fake = {"a": [{"url": "u1"}, {"url": "u2", "enabled": False}], "b": [{"url": "u3", "enabled": False}]}
        self.assertEqual(sources.enabled(fake), {"a": [{"url": "u1"}]})
        import refresh
        urls = set(refresh.urls())
        self.assertFalse(urls & bb, "refresh.py must not fetch disabled sources")
        self.assertTrue({s["url"] for s in sources.load_all()["football"]} <= urls)

    def test_extract_leaves_out_disabled_sports(self):
        d = json.load(open(os.path.join(ROOT, "data", "courses.json")))
        self.assertEqual({c["sport"] for c in d["courses"]}, {"football"})
        self.assertEqual(d["count"], len(d["courses"]))

if __name__ == "__main__":
    unittest.main()
