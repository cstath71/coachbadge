"""Courses read by a person in a normal browser on 24 Oct 2026 (sites that refuse automated visitors), France's diploma
block, and the updated reasons for Belgium, Scotland and Ireland."""
import datetime, json, os, re, shutil, subprocess, sys, tempfile, unittest
import yaml
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
DATA = json.load(open(os.path.join(ROOT, "data", "courses.json"), encoding="utf-8"))
BY_ID = {c["id"]: c for c in DATA["courses"]}
MANUAL = yaml.safe_load(open(os.path.join(ROOT, "data", "manual_courses.yaml"), encoding="utf-8"))
MANUAL = MANUAL["courses"] if isinstance(MANUAL, dict) else MANUAL
SRC = yaml.safe_load(open(os.path.join(ROOT, "data", "sources.yaml"), encoding="utf-8"))["football"]
CH = ["che-fvrz-uefa-c-1-27", "che-fvrz-uefa-c-2-27", "che-fvrz-uefa-c-3-27", "che-fvrz-uefa-c-4-27", "che-fvrz-uefa-b-2027-28"]
NL = ["nld-knvb-vc4-senioren-2027-28", "nld-knvb-vc4-jeugd-2027-28"]

def soup(rel):
    with open(os.path.join(DIST, rel), encoding="utf-8") as f: return BeautifulSoup(f.read(), "html.parser")

class TestBrowserCourses(unittest.TestCase):
    def test_all_present_as_manual_entries(self):
        ids = {m["id"] for m in MANUAL}
        for i in CH + NL:
            with self.subTest(i):
                self.assertIn(i, ids); self.assertIn(i, BY_ID)
                c = BY_ID[i]
                self.assertEqual(c["read_with"], "browser"); self.assertEqual(c["fetched_at"], "2026-10-24")
                self.assertTrue(c["source_url"].startswith("https://"))

    def test_switzerland_fields(self):
        c1 = BY_ID["che-fvrz-uefa-c-1-27"]
        self.assertEqual(c1["status"], "full")
        for i in CH[1:4]:
            c = BY_ID[i]
            self.assertEqual((c["status"], c["level"], c["deadline"]), ("open", "UEFA C", None))
            self.assertIn("2 months before", c["application_window"])
        for i in CH[:4]:
            p = BY_ID[i]["price"]
            self.assertEqual((p["amount"], p["currency"]), (350, "CHF")); self.assertIn("700", p["note"])
        b = BY_ID["che-fvrz-uefa-b-2027-28"]
        self.assertEqual((b["status"], b["deadline"], b["level"], b["price"]), ("upcoming", "2027-03-20", "UEFA B", None))
        self.assertTrue(b.get("price_note"))

    def test_switzerland_excluded_courses_absent(self):
        ch = [c for c in DATA["courses"] if c["country"] == "Switzerland"]
        self.assertEqual(sorted(c["id"] for c in ch), sorted(CH))
        for bad in ("C Basic 1", "B 1.1-26", "B-Youth", "UEFA A"): self.assertNotIn(bad, " ".join(c["title"] for c in ch))

    def test_netherlands_fields(self):
        for i in NL:
            c = BY_ID[i]
            self.assertEqual((c["level"], c["deadline"], c["status"], c["start_note"]), ("Voetbalcoach 4 (KNVB)", "2026-10-25", "open", "May/June 2027"))
            self.assertEqual((c["price"]["amount"], c["price"]["currency"]), (11585, "EUR"))
            self.assertIn("75", c["price"]["note"]); self.assertIn("315", c["price"]["note"])

    def test_netherlands_closes_by_itself_after_the_deadline(self):
        import build
        old = build.TODAY
        try:
            for day, want in (("2026-10-24", "closing_soon"), ("2026-10-25", "closing_soon"), ("2026-10-26", "closed")):
                build.TODAY = datetime.date.fromisoformat(day)
                for i in NL:
                    with self.subTest(day=day, id=i): self.assertEqual(build.status(BY_ID[i]), want)
        finally: build.TODAY = old

    def test_netherlands_page_built_on_26_october_shows_closed(self):
        tmp = tempfile.mkdtemp()
        try:
            for d in ("scripts", "data", "config", "site", "templates"):
                if os.path.isdir(os.path.join(ROOT, d)): shutil.copytree(os.path.join(ROOT, d), os.path.join(tmp, d), ignore=shutil.ignore_patterns("__pycache__"))
            for f in ("affiliates.md", "CNAME"):
                if os.path.exists(os.path.join(ROOT, f)): shutil.copy(os.path.join(ROOT, f), tmp)
            subprocess.run([sys.executable, "scripts/build.py", "--today", "2026-10-26"], cwd=tmp, check=True, capture_output=True)
            s = BeautifulSoup(open(os.path.join(tmp, "dist", "country", "netherlands.html"), encoding="utf-8").read(), "html.parser")
            self.assertIsNotNone(s.select_one("#no-open-courses"), "no NL course is open after 25 Oct")
            rows = s.select("table.courses tbody tr")
            self.assertEqual(len(rows), 2)
            for r in rows: self.assertIn("closed", r.get("class", []))
        finally: shutil.rmtree(tmp, ignore_errors=True)

    def test_refresh_keeps_and_skips_them(self):
        import refresh, sources
        urls = set(refresh.urls())
        for i in CH + NL: self.assertNotIn(BY_ID[i]["source_url"], urls)
        for s in SRC:
            if s.get("readable") == "browser": self.assertNotIn(s["url"], urls)
        self.assertTrue(set(BY_ID[i]["source_url"] for i in CH + NL) <= set(refresh.BY_HAND))

    def test_extract_keeps_manual_entries(self):
        """A refresh rebuild of courses.json (extract.py) keeps every browser-read manual course."""
        if not os.path.isdir(os.path.join(ROOT, "raw", "cache")): self.skipTest("raw/ cache not present (it is not committed)")
        tmp = tempfile.mkdtemp()
        try:
            for d in ("scripts", "data", "config"): shutil.copytree(os.path.join(ROOT, d), os.path.join(tmp, d), ignore=shutil.ignore_patterns("__pycache__"))
            os.symlink(os.path.join(ROOT, "raw"), os.path.join(tmp, "raw"))
            subprocess.run([sys.executable, "scripts/extract.py", "--today", "2026-10-31"], cwd=tmp, check=True, capture_output=True)
            ids = {c["id"] for c in json.load(open(os.path.join(tmp, "data", "courses.json"), encoding="utf-8"))["courses"]}
            self.assertTrue(set(CH + NL) <= ids)
        finally: shutil.rmtree(tmp, ignore_errors=True)

    def test_pages(self):
        ch = soup("country/switzerland.html")
        self.assertIsNone(ch.select_one("#no-open-courses"))  # UEFA C 2-27 to 4-27 have no fixed deadline
        self.assertEqual(len(ch.select("table.courses tbody tr")), 5)
        self.assertIn("350 CHF", ch.get_text())
        nl = soup("country/netherlands.html")
        self.assertEqual(len(nl.select("table.courses tbody tr")), 2)
        # empty state only once the 25 Oct deadline has passed
        self.assertEqual(nl.select_one(".board") is None, nl.select_one("#no-open-courses") is not None)
        self.assertIn("May/June 2027", nl.get_text())
        self.assertTrue(os.path.exists(os.path.join(DIST, "level", "voetbalcoach-4-knvb.html")))
        lv = soup("level/voetbalcoach-4-knvb.html").get_text()
        self.assertIn("Voetbalcoach 4 Senioren", lv); self.assertIn("Voetbalcoach 4 Jeugd", lv)

    def test_sources_updated(self):
        by = lambda ct: [s for s in SRC if s["country"] == ct]
        self.assertEqual({s["readable"] for s in by("Netherlands")}, {"browser"})
        self.assertEqual({s["readable"] for s in by("Switzerland")}, {"partial", "browser"})
        for s in by("Belgium"): self.assertIn("normal browser the pages stayed blank", s["reason"])
        self.assertIn("under construction", by("Scotland")[0]["note"]); self.assertIn("MyComet", by("Scotland")[0]["note"])
        self.assertIn("No Courses", by("Ireland")[0]["note"])
        fr = {s["association"]: s for s in by("France")}
        self.assertEqual(fr["FFF (France)"]["readable"], "browser"); self.assertIn("no session dates", fr["FFF (France)"]["note"])
        self.assertEqual(fr["IR2F (France)"]["readable"], "no")

class TestFranceDiplomas(unittest.TestCase):
    def test_block_is_information_not_courses(self):
        self.assertFalse([c for c in DATA["courses"] if c["country"] == "France"])
        s = soup("country/france.html")
        self.assertIsNotNone(s.select_one("#no-open-courses"))
        box = s.select_one("#diplomas"); self.assertIsNotNone(box)
        t = box.get_text(" ", strip=True)
        for want in ("BMF", "UEFA B", "€2,498", "BEF", "UEFA A", "€3,054", "BEFF", "UEFA Elite Youth A", "€15,680", "BEPF", "UEFA Pro", "€24,640", "no session dates", "March/April 2026", "€50"):
            self.assertIn(want, t)
        self.assertEqual(len(box.select("a[href^='https://maformation.fff.fr/formation/']")), 4)
        for sc in s.select('script[type="application/ld+json"]'): self.assertNotIn('"Course"', sc.string)
        self.assertNotRegex(t.lower(), r"\bofficial\b")

    def test_diploma_evidence_on_browser_snapshot(self):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        from test_site import browser_snapshot, norm
        info = yaml.safe_load(open(os.path.join(ROOT, "data", "diplomas.yaml"), encoding="utf-8"))
        for ct, v in info.items():
            for d in v["diplomas"]:
                snap = browser_snapshot(d["url"])
                if snap is None: continue
                for ev in d["evidence"]:
                    with self.subTest(d["short"], ev=ev): self.assertIn(norm(ev), snap)

if __name__ == "__main__":
    unittest.main()
