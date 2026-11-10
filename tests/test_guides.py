"""Guides (licence and course comparisons): built from data only, linked, in sitemap/llms, affiliate block with disclosure. Offline."""
import json, os, re, unittest
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
BASE = json.load(open(os.path.join(ROOT, "config", "site.json")))["base_url"].rstrip("/") + "/"
COURSES = json.load(open(os.path.join(DIST, "data", "courses.json")))["courses"]
GUIDES = ["guides/uefa-c-vs-uefa-b.html", "guides/uefa-licence-pathway-by-country.html", "guides/uefa-c-licence-cost-by-country.html"]
DISCLOSURE = "Some links are affiliate links: if you buy through them, CoachBadge may earn a commission at no extra cost to you."
S = lambda p: BeautifulSoup(open(os.path.join(DIST, p)).read(), "html.parser")
CUR = {"GBP": "£", "EUR": "€"}
def money(a, cur):
    a = int(a) if float(a).is_integer() else a
    return f"{CUR[cur]}{a:,}" if cur in CUR else f"{a:,} {cur}"

class TestGuides(unittest.TestCase):
    def test_pages_linked_and_listed(self):
        sm = open(os.path.join(DIST, "sitemap.xml")).read(); llms = open(os.path.join(DIST, "llms.txt")).read()
        hub = S("guides.html"); self.assertIn(BASE + "guides.html", sm)
        self.assertIsNotNone(S("index.html").select_one('nav.main a[href="guides.html"]'))
        for p in GUIDES:
            with self.subTest(p):
                self.assertIn(BASE + p, sm); self.assertIn(BASE + p, llms)
                self.assertIsNotNone(hub.find("a", href=p))
                types = [json.loads(x.string).get("@type") for x in S(p).find_all("script", type="application/ld+json")]
                self.assertIn("Article", types); self.assertIn("BreadcrumbList", types)

    def test_affiliate_block_with_disclosure(self):
        for p in GUIDES + ["guides.html"]:
            with self.subTest(p):
                box = S(p).select_one("aside.resources"); self.assertIsNotNone(box)
                self.assertIn(DISCLOSURE, box.get_text(" "))
                self.assertEqual(len(box.find_all("a", rel=lambda r: r and "sponsored" in r)), 4)

    def test_cost_page_prices_come_from_data(self):
        s = S("guides/uefa-c-licence-cost-by-country.html")
        rows = s.select("main table tbody tr")
        priced = [c for c in COURSES if c["level"] == "UEFA C" and c.get("price") and c["price"].get("amount") is not None]
        self.assertTrue(rows); self.assertEqual(sum(int(r.find_all("td")[4].get_text()) for r in rows), len(priced))
        allowed = {money(c["price"]["amount"], c["price"]["currency"]) for c in priced}
        srcs = {c["source_url"] for c in priced}
        for r in rows:
            td = r.find_all("td")
            self.assertIn(td[2].get_text(strip=True), allowed)
            self.assertIn(td[5].find("a")["href"], srcs)

    def test_c_vs_b_counts_match_data(self):
        t = re.sub(r"\s+", " ", S("guides/uefa-c-vs-uefa-b.html").select_one("#summary").get_text())
        c = len([x for x in COURSES if x["level"] == "UEFA C"]); b = len([x for x in COURSES if x["level"] == "UEFA B"])
        self.assertIn(f"tracks {c} UEFA C courses and {b} UEFA B courses", t)

    def test_answer_first_guides(self):
        """Pathway and C vs B open with 2 to 3 dated sentences, a visible date, and a FAQ that matches FAQPage."""
        order = "UEFA C, UEFA B, UEFA A, UEFA Elite Youth A and UEFA Pro"
        for p, needle in (("guides/uefa-licence-pathway-by-country.html", order),
                          ("guides/uefa-c-vs-uefa-b.html", "does not state entry rules")):
            with self.subTest(p):
                s = S(p)
                summ = re.sub(r"\s+", " ", s.select_one("#summary").get_text()).strip()
                self.assertTrue(summ.startswith("As of "))
                self.assertIn(needle, summ)
                n = len([x for x in re.split(r"(?<=[.])\s+", summ) if x])
                self.assertGreaterEqual(n, 2); self.assertLessEqual(n, 3)
                self.assertIsNone(re.search(r"[\u2013\u2014]", summ), "no en or em dash in the new summary")
                art = [json.loads(x.string) for x in s.find_all("script", type="application/ld+json")]
                art = [o for o in art if o.get("@type") == "Article"][0]
                tm = s.select_one("p.updated time")
                self.assertEqual(tm["datetime"], art["dateModified"])
                self.assertIn(tm.get_text(), s.select_one("p.updated").get_text())
                self.assertIs(s.select_one("#summary").find_next("p"), s.select_one("p.updated"))
                faq = [o for o in (json.loads(x.string) for x in s.find_all("script", type="application/ld+json")) if o.get("@type") == "FAQPage"][0]
                box = s.select_one("section.faq#faq")
                self.assertGreaterEqual(len(faq["mainEntity"]), 2)
                self.assertEqual(s.select_one("p.updated").find_next("section").get("id"), "faq")
                vis = re.sub(r"\s+", " ", box.get_text())
                for q in faq["mainEntity"]:
                    self.assertIn(q["name"], [h.get_text() for h in box.select("h3")])
                    self.assertIn(re.sub(r"\s+", " ", q["acceptedAnswer"]["text"]), vis)
                self.assertIsNone(re.search(r"official|mandatory|primelogic|stathopoulos", summ, re.I))

    def test_no_banned_words(self):
        for p in GUIDES + ["guides.html"]:
            self.assertIsNone(re.search(r"official|mandatory|primelogic|stathopoulos|basketball", open(os.path.join(DIST, p)).read(), re.I), p)

if __name__ == "__main__":
    unittest.main()
