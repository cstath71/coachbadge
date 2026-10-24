"""SEO + answer-engine output (scripts/seo.py via scripts/build.py). Run after python3 scripts/build.py."""
import datetime, glob, html, json, os, re, struct, sys, tempfile, unittest
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
CFG = json.load(open(os.path.join(ROOT, "config", "site.json")))
BASE = CFG["base_url"]
PUB = json.load(open(os.path.join(DIST, "data", "courses.json")))
COURSES = PUB["courses"]
LIVE = [c for c in COURSES if c["display_status"] in ("open", "closing_soon")]
R = lambda p: open(os.path.join(DIST, p)).read()
S = lambda p: BeautifulSoup(R(p), "html.parser")
T = lambda s: re.sub(r"\s+", " ", s).strip()
HTML = sorted(os.path.relpath(p, DIST) for p in glob.glob(os.path.join(DIST, "**", "*.html"), recursive=True))
NOINDEX = {"unsubscribe.html", "404.html"}
INDEXABLE = [p for p in HTML if p not in NOINDEX]
AREA = [p for p in HTML if p.startswith(("country/", "level/"))]
def url_of(p): return BASE + ("" if p == "index.html" else p)
def lds(p):
    out = []
    for s in S(p).select('script[type="application/ld+json"]'):
        o = json.loads(s.string)
        out += o.get("@graph", [o])
    return out
def of_type(p, t): return [o for o in lds(p) if o.get("@type") == t]
def walk(o):
    if isinstance(o, dict):
        for v in o.values(): yield v; yield from walk(v)
    elif isinstance(o, list):
        for v in o: yield v; yield from walk(v)

class TestRobots(unittest.TestCase):
    def test_allows_all_and_ai_crawlers(self):
        t = R("robots.txt")
        self.assertNotIn("Disallow", t)
        self.assertTrue(t.startswith("User-agent: *\nAllow: /\n"))
        for b in ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "PerplexityBot",
                  "Google-Extended", "Applebot-Extended", "Bingbot", "CCBot"):
            self.assertRegex(t, rf"(?m)^User-agent: {re.escape(b)}$")
        self.assertIn(f"\nSitemap: {BASE}sitemap.xml\n", t)

class TestLlms(unittest.TestCase):
    def test_llms_txt_facts_from_data(self):
        t = R("llms.txt")
        self.assertTrue(t.startswith(f"# {CFG['brand']}\n\n> {CFG['tagline']}."))
        self.assertIn(f"{len(LIVE)} football coaching courses in Europe are open", t)
        self.assertIn(f"tracks {len(COURSES)} courses", t)
        self.assertIn(f"Data last checked: {PUB['generated']}", t)
        self.assertIn("weekly", t)
        for p in ("", "methodology.html", "countries.html", "levels.html", "resources.html", "data/courses.json", "llms-full.txt"):
            self.assertIn(f"({BASE}{p})", t)
        for p in AREA: self.assertIn(f"({BASE}{p})", t)
        for u in re.findall(rf"\]\({re.escape(BASE)}([^)]*)\)", t):
            self.assertTrue(os.path.exists(os.path.join(DIST, u or "index.html")), u)

    def test_llms_full_lists_every_course(self):
        t = R("llms-full.txt")
        self.assertTrue(t.startswith(R("llms.txt")))
        self.assertIn(f"## All {len(COURSES)} tracked courses", t)
        for c in COURSES:
            self.assertIn(f"- {c['title']}; ", t); self.assertIn(c["source_url"], t)

    def test_no_banned_words_or_owner(self):
        for f in ("llms.txt", "llms-full.txt"):
            self.assertIsNone(re.search(r"official|mandatory|primelogic|stathopoulos|cstath|basketball", R(f), re.I), f)

class TestStructuredData(unittest.TestCase):
    def test_all_jsonld_parses_and_has_no_nulls(self):
        for p in HTML:
            with self.subTest(p):
                for o in lds(p):
                    self.assertNotIn(None, list(walk(o)), "no null values in JSON-LD")
                    self.assertNotIn("", [v for v in walk(o) if isinstance(v, str)])

    def test_home_website_and_org(self):
        ws, = of_type("index.html", "WebSite"); org, = of_type("index.html", "Organization")
        self.assertEqual(ws["url"], BASE); self.assertEqual(ws["name"], CFG["brand"]); self.assertEqual(ws["publisher"]["@id"], org["@id"])
        self.assertEqual(org["name"], CFG["brand"]); self.assertEqual(org["url"], BASE)
        self.assertTrue(org["logo"].startswith(BASE)); self.assertTrue(os.path.exists(os.path.join(DIST, org["logo"][len(BASE):])))
        blob = json.dumps(org)
        for bad in ("Person", "founder", "PrimeLogic", "Stathopoulos", "Switzerland", "address"): self.assertNotIn(bad, blob)

    def test_breadcrumbs_on_every_subpage(self):
        for p in INDEXABLE:
            with self.subTest(p):
                bc = of_type(p, "BreadcrumbList")
                if p == "index.html": self.assertEqual(bc, []); continue
                self.assertEqual(len(bc), 1)
                items = bc[0]["itemListElement"]
                self.assertEqual(items[0]["item"], BASE); self.assertEqual(items[-1]["item"], url_of(p))
                self.assertEqual([i["position"] for i in items], list(range(1, len(items) + 1)))
                for i in items: self.assertTrue(os.path.exists(os.path.join(DIST, i["item"][len(BASE):] or "index.html")))
                vis = S(p).select_one("nav.crumbs")
                self.assertEqual([li.get_text() for li in vis.select("li")], [i["name"] for i in items])

    def test_item_lists_match_page(self):
        for p in AREA + ["index.html"]:
            with self.subTest(p):
                il = of_type(p, "ItemList"); rows = S(p).select("table.courses tbody tr")
                if not rows and p != "index.html": self.assertEqual(il, []); continue
                il, = il
                n = len(S(p).select(".board .card")) if p == "index.html" else len(rows)
                self.assertEqual(il["numberOfItems"], n); self.assertEqual(len(il["itemListElement"]), n)

    def test_courses_only_real_fields(self):
        by = {}
        for c in COURSES: by.setdefault((c["title"], c["source_url"]), []).append(c)
        sd = lambda x: x.get("hasCourseInstance", {}).get("startDate")
        seen = 0
        for p in AREA:
            for il in of_type(p, "ItemList"):
                for li in il["itemListElement"]:
                    x = li["item"]; seen += 1
                    c = [c for c in by[(x["name"], x["url"])] if (c.get("start_date") if c.get("start_date") and len(c["start_date"]) == 10 else None) == sd(x)][0]
                    self.assertEqual(x["@type"], "Course"); self.assertEqual(x["provider"]["name"], c["provider"])
                    self.assertEqual("offers" in x, bool(c.get("price") and c["price"].get("amount") is not None))
                    if "offers" in x:
                        self.assertEqual(x["offers"]["price"], c["price"]["amount"]); self.assertEqual(x["offers"]["priceCurrency"], c["price"]["currency"])
                    inst = x.get("hasCourseInstance", {})
                    self.assertEqual(inst.get("startDate"), c.get("start_date") if c.get("start_date") and len(c["start_date"]) == 10 else None)
                    if "location" in inst: self.assertEqual(inst["location"]["name"], c["location"])
                    else: self.assertFalse(c.get("location"))
        self.assertGreaterEqual(seen, len(COURSES))

    def test_faq_ld_matches_visible_faq(self):
        for p in ["index.html"] + AREA:
            with self.subTest(p):
                faq, = of_type(p, "FAQPage")
                box = S(p).select_one("section.faq#faq"); vis = T(box.get_text(" "))
                self.assertGreaterEqual(len(faq["mainEntity"]), 6 if p == "index.html" else 2)
                for q in faq["mainEntity"]:
                    self.assertIn(q["name"], [h.get_text() for h in box.select("h3")])
                    self.assertIn(T(q["acceptedAnswer"]["text"]), T(box.get_text()))
        for p in INDEXABLE:
            if not S(p).select_one("section.faq"): self.assertEqual(of_type(p, "FAQPage"), [], p)

class TestAnswerFirst(unittest.TestCase):
    def test_summaries_at_top(self):
        for p in ["index.html"] + AREA:
            with self.subTest(p):
                s = S(p); summ = s.select_one("#summary")
                self.assertIsNotNone(summ); self.assertTrue(summ.get_text().startswith("As of "))
                self.assertIs(summ.find_previous("h1"), s.h1, "summary sits right under the h1")
        home = S("index.html").select_one("#summary").get_text()
        self.assertIn(f"{len(LIVE)} football coaching courses in Europe are open", home)
        self.assertIn(f"tracks {len(COURSES)} courses", home)

    def test_area_summary_counts(self):
        for p in AREA:
            with self.subTest(p):
                s = S(p); rows = s.select("table.courses tbody tr")
                live = [r for r in rows if r["data-status"] in ("open", "closing_soon")]
                summ = s.select_one("#summary").get_text()
                if not rows: self.assertIn("has not found", summ); continue
                if live: self.assertIn(f"{len(live)} of the {len(rows)} ", summ)
                else: self.assertRegex(summ, r"none of the|the one .* is not open")

    def test_home_faq_numbers(self):
        faq = {q["name"]: q["acceptedAnswer"]["text"] for q in of_type("index.html", "FAQPage")[0]["mainEntity"]}
        priced = [c for c in COURSES if c.get("price") and c["price"].get("amount") is not None]
        self.assertIn(f"{len(priced)} of the {len(COURSES)} tracked courses", faq["Are course prices listed?"])
        self.assertIn(f"{len(LIVE)} courses are open", faq["Which football coaching courses are open right now?"])
        self.assertIn(CFG["disclaimer"], faq[f"What is {CFG['brand']}?"])

class TestMeta(unittest.TestCase):
    def test_unique_titles_and_descriptions(self):
        titles, descs = {}, {}
        for p in INDEXABLE:
            s = S(p); t = s.title.get_text(); d = s.select_one('meta[name="description"]')["content"]
            with self.subTest(p):
                self.assertTrue(20 <= len(d) <= 300, (len(d), d)); self.assertNotIn(t, titles, (p, titles.get(t))); self.assertNotIn(d, descs, (p, descs.get(d)))
            titles[t] = p; descs[d] = p

    def test_head_tags(self):
        for p in HTML:
            s = S(p)
            with self.subTest(p):
                self.assertEqual(s.html["lang"], "en")
                self.assertEqual(s.select_one('link[rel="canonical"]')["href"], url_of(p))
                self.assertEqual(s.select_one('meta[property="og:image"]')["content"], BASE + "og.png")
                self.assertEqual(s.select_one('meta[name="twitter:card"]')["content"], "summary_large_image")
                for k in ("og:title", "og:description", "og:url", "og:image:alt"): self.assertTrue(s.select_one(f'meta[property="{k}"]')["content"])
                for k in ("twitter:title", "twitter:description", "twitter:image"): self.assertTrue(s.select_one(f'meta[name="{k}"]')["content"])
                want = "noindex" if p in NOINDEX else "index,follow"
                self.assertTrue(s.select_one('meta[name="robots"]')["content"].startswith(want))

    def test_no_index_html_links(self):
        for p in HTML:
            for a in S(p).select("a[href]"):
                with self.subTest(p, href=a["href"]): self.assertNotRegex(a["href"], r"(^|/)index\.html")

    def test_headings(self):
        for p in HTML:
            with self.subTest(p):
                hs = [int(h.name[1]) for h in S(p).find_all(re.compile(r"^h[1-6]$"))]
                self.assertEqual(hs.count(1), 1); self.assertEqual(hs[0], 1) if p not in ("index.html",) else None
                for a, b in zip(hs, hs[1:]): self.assertLessEqual(b - a, 1, f"heading jumps from h{a} to h{b}")

    def test_images_have_alt(self):
        for p in HTML:
            for im in S(p).find_all("img"): self.assertTrue(im.get("alt"), p)

    def test_share_images(self):
        for f, wh in (("og.png", (1200, 630)), ("logo-512.png", (512, 512))):
            b = open(os.path.join(DIST, f), "rb").read(24)
            self.assertEqual(b[:8], b"\x89PNG\r\n\x1a\n"); self.assertEqual(struct.unpack(">II", b[16:24]), wh)

    def test_verification_tags_only_when_set(self):
        for p in HTML:
            s = R(p)
            for k, cfg in (("google-site-verification", "google_site_verification"), ("msvalidate.01", "msvalidate")):
                self.assertEqual(f'name="{k}"' in s, bool(CFG.get(cfg)), (p, k))
        import build
        old = build.DIST, build.VERIFY, list(build.PAGES)
        with tempfile.TemporaryDirectory() as d:
            build.DIST = d; build.VERIFY = [("google-site-verification", "g-tok"), ("msvalidate.01", "")]
            try: build.page("x.html", "X", "Test page.", "<main><h1>X</h1></main>")
            finally: build.DIST, build.VERIFY = old[0], old[1]; build.PAGES[:] = old[2]
            h = open(os.path.join(d, "x.html")).read()
        self.assertIn('<meta name="google-site-verification" content="g-tok">', h); self.assertNotIn("msvalidate", h)

class TestSitemap(unittest.TestCase):
    def test_sitemap_is_every_indexable_page(self):
        sm = R("sitemap.xml")
        locs = re.findall(r"<loc>(.*?)</loc>", sm)
        self.assertEqual(sorted(locs), sorted(url_of(p) for p in INDEXABLE))
        self.assertIn(BASE + "resources.html", locs)
        for p in NOINDEX: self.assertNotIn(BASE + p, sm)
        gen = datetime.date.fromisoformat(PUB["generated"])
        mods = re.findall(r"<lastmod>(.*?)</lastmod>", sm); self.assertEqual(len(mods), len(locs))
        for m in mods: self.assertLessEqual(datetime.date.fromisoformat(m), gen)

class TestIndexNow(unittest.TestCase):
    def test_key_file_and_payload(self):
        from seo import INDEXNOW_KEY as K
        self.assertRegex(K, r"^[0-9a-f]{32}$")
        self.assertEqual(R(f"{K}.txt"), K)
        import indexnow
        urls, body = indexnow.payload()
        self.assertEqual(body["host"], "coachbadge.com"); self.assertEqual(body["keyLocation"], f"{BASE}{K}.txt")
        self.assertEqual(urls, re.findall(r"<loc>(.*?)</loc>", R("sitemap.xml")))

if __name__ == "__main__":
    unittest.main()
