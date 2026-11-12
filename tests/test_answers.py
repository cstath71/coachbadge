"""Question pages: headline figures are recomputed from the built course data, and FAQ JSON-LD
equals the visible FAQ text. Run after python3 scripts/build.py."""
import datetime, html, json, os, re, unittest
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
CFG = json.load(open(os.path.join(ROOT, "config", "site.json")))
BASE = CFG["base_url"].rstrip("/") + "/"
PUB = json.load(open(os.path.join(DIST, "data", "courses.json")))
COURSES = PUB["courses"]
TODAY = datetime.date.fromisoformat(PUB["build_date"])
GENERATED = PUB["generated"][:10]
CLOSING_DAYS = 30  # scripts/build.py CLOSING_DAYS
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
FULL_MONTHS = "January February March April May June July August September October November December".split()
CUR = {"GBP": "£", "EUR": "€"}
LABEL = {"open": "Open", "closing_soon": "Closing soon", "full": "Full / waitlist", "closed": "Closed",
         "upcoming": "Upcoming", "unknown": "Check provider"}
PATHWAY = ["UEFA C", "UEFA B", "UEFA A", "UEFA Pro"]
ELITE = "UEFA Elite Youth A"
# Question wording and URL. These are the pages an answer engine should cite.
QUESTIONS = [
    ("answers/uefa-football-coaching-licence-pathway.html",
     "UEFA football coaching licence pathway C B A Pro order"),
    ("cost/uefa-c.html",
     "How much does a UEFA C licence cost in different countries"),
    ("answers/uefa-b-open-applications-europe-2026.html",
     "UEFA B football coaching courses open for applications Europe 2026"),
    ("answers/uefa-c-vs-uefa-b-licence-difference.html",
     "UEFA C vs UEFA B licence difference football coaching"),
    ("answers/open-football-coaching-courses-europe-deadlines.html",
     "Where to find open football coaching courses in Europe with application deadlines"),
    ("answers/uefa-a-licence-application-deadline-2027.html",
     "UEFA A licence course application deadline 2027"),
    ("answers/uefa-b-coaching-course-sweden-2027.html",
     "UEFA B coaching course Sweden 2027 how to apply"),
    ("answers/cheapest-country-uefa-c-licence.html",
     "Cheapest country to get a UEFA C coaching licence"),
]

def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()

def pdate(s):
    if not s or len(s) < 10:
        return None
    try:
        return datetime.date.fromisoformat(s[:10])
    except ValueError:
        return None

def fdate(s):
    if not s:
        return ""
    p = s.split("-")
    if len(p) == 3:
        return f"{int(p[2])} {MONTHS[int(p[1]) - 1]} {p[0]}"
    if len(p) == 2:
        return f"{MONTHS[int(p[1]) - 1]} {p[0]}"
    return s

def money(amount, currency):
    a = int(amount) if float(amount).is_integer() else amount
    sym = CUR.get(currency)
    return f"{sym}{a:,}" if sym else f"{a:,} {currency}"

def and_list(xs):
    xs = list(xs)
    if not xs:
        return ""
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]

def counted(n, one, many=None):
    return f"{n} {one if n == 1 else (many or one + 's')}"

def for_copy(s):
    return re.sub(r"\s+", " ", (s or "").replace("\u2013", " - ").replace("\u2014", " - ")).strip()

def display(c):
    """Same rule as scripts/build.py status(), from the raw status, the deadline and the build date."""
    s = c["status"]
    if s == "open":
        d = pdate(c.get("deadline"))
        if d and d < TODAY:
            return "closed"
        if d and (d - TODAY).days <= CLOSING_DAYS:
            return "closing_soon"
    return s

def is_live(c):
    return display(c) in ("open", "closing_soon")

def amount_of(c):
    return (c.get("price") or {}).get("amount")

def priced(cs):
    return [c for c in cs if amount_of(c) is not None]

def at(level):
    return [c for c in COURSES if c["level"] == level]

def price_range(cs):
    by = {}
    for c in priced(cs):
        by.setdefault(c["price"]["currency"], []).append(amount_of(c))
    out = []
    for cur, xs in sorted(by.items()):
        lo, hi = money(min(xs), cur), money(max(xs), cur)
        out.append(lo if lo == hi else f"{lo} to {hi}")
    return out

def both_dates(cs):
    n = 0
    for c in cs:
        a, b = pdate(c.get("start_date")), pdate(c.get("end_date"))
        if a and b and b >= a:
            n += 1
    return n

def lowest_phrase(cs):
    fees = priced(cs)
    amount = min(amount_of(c) for c in fees)
    winners = [c for c in fees if amount_of(c) == amount]
    bits = []
    for cur in sorted({c["price"]["currency"] for c in winners}):
        countries = sorted({c["country"] for c in winners if c["price"]["currency"] == cur})
        bits.append(f"{money(amount, cur)} in {and_list(countries)}")
    return and_list(bits), winners

def per_currency(cs):
    best = {}
    for c in priced(cs):
        cur, amt = c["price"]["currency"], amount_of(c)
        rec = best.get(cur)
        if rec is None or amt < rec["amount"]:
            best[cur] = {"amount": amt, "countries": {c["country"]}}
        elif amt == rec["amount"]:
            rec["countries"].add(c["country"])
    bits = [f"{money(best[cur]['amount'], cur)} in {and_list(sorted(best[cur]['countries']))}" for cur in sorted(best)]
    return and_list(bits)

def sweden_b_2027():
    out = []
    for c in COURSES:
        if c["country"] != "Sweden" or c["level"] != "UEFA B":
            continue
        if ((c.get("start_date") or "").startswith("2027") or "2027" in (c.get("title") or "")
                or (c.get("deadline") or "").startswith("2027")):
            out.append(c)
    return out

def lists(n, rest):
    return f"{n} {'lists' if n == 1 else 'list'} {rest}"

def soup(path):
    return BeautifulSoup(open(os.path.join(DIST, path)).read(), "html.parser")

def lds(s):
    out = []
    for sc in s.select('script[type="application/ld+json"]'):
        o = json.loads(sc.string)
        out.extend(o.get("@graph", [o]))
    return out

def of_type(s, t):
    return [o for o in lds(s) if o.get("@type") == t]

GEN = fdate(GENERATED)
MONTH_YEAR = f"{FULL_MONTHS[int(GENERATED[5:7]) - 1]} {GENERATED[:4]}"


class TestAnswerPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for c in COURSES:
            got = display(c)
            if got != c["display_status"]:
                raise AssertionError(f"{c['id']}: recomputed {got}, page data says {c['display_status']}")

    def test_status_rule_matches_published_display_status(self):
        self.assertTrue(COURSES)
        self.assertTrue(all(display(c) == c["display_status"] for c in COURSES))

    def test_homepage_links_questions(self):
        home = soup("index.html")
        links = home.select("ul.answers a")
        self.assertEqual([(a["href"], a.get_text()) for a in links], QUESTIONS)
        self.assertIsNotNone(home.select_one('nav.main a[href="answers.html"]'))
        guides = open(os.path.join(DIST, "guides.html")).read()
        for path, _h in QUESTIONS:
            self.assertIn(path, guides)

    def test_each_question_page(self):
        sm = dict(re.findall(r"<loc>(.*?)</loc><lastmod>(.*?)</lastmod>", open(os.path.join(DIST, "sitemap.xml")).read()))
        llms = open(os.path.join(DIST, "llms.txt")).read()
        full = open(os.path.join(DIST, "llms-full.txt")).read()
        self.assertTrue(full.startswith(llms))
        for path, h1 in QUESTIONS:
            with self.subTest(path):
                raw = open(os.path.join(DIST, path)).read()
                s = BeautifulSoup(raw, "html.parser")
                self.assertEqual(s.h1.get_text(), h1)
                self.assertIn(h1, s.title.get_text())
                summary = norm(s.select_one("#summary").get_text())
                self.assertTrue(summary)
                self.assertIn(html.escape(summary, quote=True), raw)
                self.assertIsNone(s.select_one("script #summary"))
                self.assertIsNone(re.search(r"[\u2013\u2014]", summary))
                self.assertIsNone(re.search(r"official|mandatory|primelogic|stathopoulos", summary, re.I))
                faq_ld, = of_type(s, "FAQPage")
                box = s.select_one("section.faq#faq")
                hs, ps = box.select("h3"), box.select("p")
                self.assertEqual(len(hs), len(ps))
                self.assertGreaterEqual(len(hs), 3)
                self.assertEqual(len(faq_ld["mainEntity"]), len(hs))
                for h, p, q in zip(hs, ps, faq_ld["mainEntity"]):
                    self.assertEqual(h.get_text(), q["name"])
                    self.assertEqual(norm(p.get_text()), norm(q["acceptedAnswer"]["text"]))
                    self.assertIsNone(re.search(r"[\u2013\u2014]", h.get_text() + p.get_text()))
                self.assertEqual(hs[0].get_text(), h1)
                self.assertEqual(norm(ps[0].get_text()), summary)
                ds, = of_type(s, "Dataset")
                self.assertEqual(ds["dateModified"], GENERATED)
                self.assertEqual(ds["license"], BASE + "terms.html")
                self.assertEqual(norm(ds["description"]), summary)
                art, = of_type(s, "Article")
                self.assertEqual(art["dateModified"], GENERATED)
                self.assertEqual(s.select_one("p.updated time")["datetime"], GENERATED)
                self.assertIn(BASE + path, sm)
                self.assertLessEqual(sm[BASE + path], GENERATED)
                marker = f"[{h1}]({BASE}{path}): "
                line = next(ln for ln in llms.splitlines() if marker in ln)
                self.assertEqual(norm(line.split(marker, 1)[1]), summary)
                self.assertIn(BASE + path, full)
                others = [p for p, _h in QUESTIONS if p != path]
                rel = s.select_one("ul.answers")
                hrefs = [a["href"] for a in rel.select("a")]
                for other in others:
                    self.assertTrue(any(other in href for href in hrefs), other)

    def test_pathway_counts(self):
        s = soup(QUESTIONS[0][0])
        summary = norm(s.select_one("#summary").get_text())
        bits = [f"{len(at(lv))} {lv} courses" for lv in PATHWAY]
        self.assertIn("UEFA C, then UEFA B, then UEFA A, then UEFA Pro.", summary)
        self.assertIn(f"This data has {and_list(bits)}.", summary)
        self.assertIn(f"UEFA Elite Youth A is a separate level in this data ({len(at(ELITE))} courses).", summary)
        self.assertIn("does not set entry rules, required hours or experience", summary)
        open_bits = [f"{lv}: {len([c for c in at(lv) if is_live(c)])} open of {len(at(lv))}" for lv in PATHWAY]
        faq = {q["name"]: q["acceptedAnswer"]["text"] for q in of_type(s, "FAQPage")[0]["mainEntity"]}
        self.assertEqual(norm(faq["How many of those courses are open for applications?"]),
                         f"As of {GEN}, {and_list(open_bits)}.")
        for lv in PATHWAY + [ELITE]:
            row = s.select_one(f'#pathway tr[data-level="{lv}"]')
            cs = at(lv)
            live_n = len([c for c in cs if is_live(c)])
            self.assertEqual(int(row["data-tracked"]), len(cs))
            self.assertEqual(int(row["data-open"]), live_n)
            cells = row.find_all("td")
            self.assertEqual(int(cells[2].get_text()), len(cs))
            self.assertEqual(int(cells[3].get_text()), live_n)
        shown = []
        for lv in PATHWAY + [ELITE]:
            shown.extend(at(lv))
        self.assertEqual(of_type(s, "ItemList")[0]["numberOfItems"], len(shown))
        self.assertEqual(self._lastmod(QUESTIONS[0][0]), max(c["fetched_at"][:10] for c in shown))
        import yaml
        dips = yaml.safe_load(open(os.path.join(ROOT, "data", "diplomas.yaml")))
        text = s.select_one("#diplomas").get_text(" ")
        for info in dips.values():
            for d in info["diplomas"]:
                self.assertIn(d["short"], text)
                self.assertIn(d["uefa"], text)
                self.assertIsNotNone(s.select_one(f'#diplomas a[href="{d["url"]}"]'))

    def test_cost_table_and_lowest_fee(self):
        all_c = at("UEFA C")
        fees, missing = priced(all_c), [c for c in all_c if amount_of(c) is None]
        countries = sorted({c["country"] for c in fees})
        phrase, winners = lowest_phrase(all_c)
        for path in (QUESTIONS[1][0], QUESTIONS[7][0]):
            with self.subTest(path):
                s = soup(path)
                summary = norm(s.select_one("#summary").get_text())
                self.assertIn(f"{len(fees)} of the {len(all_c)} UEFA C courses" if path.endswith("uefa-c.html") and "cost/" in path else phrase, summary)
                self.assertIn(phrase, summary)
                self.assertIn(f"{len(missing)} UEFA C courses list no fee amount.", summary)
                self.assertIn(and_list(countries), summary)
                rows = s.select("#fees tbody tr")
                self.assertEqual(sum(int(r["data-courses"]) for r in rows), len(fees))
                for tr in rows:
                    provider = tr.find_all("td")[1].get_text(strip=True)
                    amount = float(tr["data-amount"])
                    cur = tr["data-currency"]
                    note_cell = tr.find_all("td")[3].get_text(strip=True)
                    group = []
                    for c in fees:
                        if c["country"] != tr["data-country"] or c["provider"] != provider or c["price"]["currency"] != cur:
                            continue
                        if float(amount_of(c)) != amount:
                            continue
                        note = for_copy(c["price"].get("note") or "")
                        if (note if note else "Not stated") == note_cell:
                            group.append(c)
                    self.assertEqual(len(group), int(tr["data-courses"]))
                    self.assertEqual(tr.find_all("td")[2].get_text(strip=True), money(amount, cur))
                    self.assertEqual(tr.find_all("td")[4].get_text(strip=True), tr["data-courses"])
                    self.assertEqual({a["href"] for a in tr.find_all("a")}, {c["source_url"] for c in group})
                    self.assertEqual(tr.find_all("td")[6].get_text(strip=True), fdate(max(c["fetched_at"][:10] for c in group)))
                ids = [tr["data-id"] for tr in s.select("#no-fee tbody tr")]
                self.assertEqual(sorted(ids), sorted(c["id"] for c in missing))
                for c in missing:
                    if c.get("price_note"):
                        self.assertIn(for_copy(c["price_note"]), s.select_one("#no-fee").get_text())
                self.assertEqual(of_type(s, "ItemList")[0]["numberOfItems"], len(all_c))
                self.assertEqual(self._lastmod(path), max(c["fetched_at"][:10] for c in all_c))
        cheap = norm(soup(QUESTIONS[7][0]).select_one("#summary").get_text())
        self.assertTrue(cheap.startswith(f"In CoachBadge's {MONTH_YEAR} data, the lowest listed UEFA C fee is {phrase}."))
        providers = and_list(sorted({c["provider"] for c in winners}))
        self.assertIn(f"on {len(winners)} courses from {providers}", cheap)
        self.assertIn(f"The lowest listed fee in each currency is {per_currency(all_c)}.", cheap)
        self.assertIn("Amounts are not converted between currencies.", cheap)
        self.assertIn("Provider notes are not used as the fee amount.", cheap)
        for note in sorted({for_copy(c["price"].get("note") or "") for c in fees if c["price"].get("note")}):
            self.assertIn(note, cheap)
        cost = norm(soup(QUESTIONS[1][0]).select_one("#summary").get_text())
        self.assertIn(f"in {counted(len(countries), 'country', 'countries')}: {and_list(countries)}.", cost)
        self.assertIn(f"The lowest listed fee is {phrase}.", cost)

    def test_open_uefa_b_europe(self):
        courses = at("UEFA B")
        live = [c for c in courses if is_live(c)]
        d2026 = [c for c in live if (c.get("deadline") or "").startswith("2026")]
        later = [c for c in live if c.get("deadline") and not c["deadline"].startswith("2026")]
        none = [c for c in live if not c.get("deadline")]
        s = soup(QUESTIONS[2][0])
        summary = norm(s.select_one("#summary").get_text())
        self.assertIn(f"{len(live)} of the {len(courses)} UEFA B football coaching courses", summary)
        self.assertIn("open for applications or booking in Europe.", summary)
        fragment = (f"Of those {len(live)}, {lists(len(d2026), 'an application deadline in 2026')}, "
                    f"{lists(len(later), 'a deadline after 2026')}, and {lists(len(none), 'no deadline')}.")
        self.assertIn(fragment, summary)
        self.assertIn(f"The open courses are in {and_list(sorted({c['country'] for c in live}))}.", summary)
        self.assertIn(f"within {CLOSING_DAYS} days.", summary)
        ids = [tr["data-id"] for tr in s.select("#open-courses tbody tr")]
        self.assertEqual(sorted(ids), sorted(c["id"] for c in live))
        self.assertEqual(of_type(s, "ItemList")[0]["numberOfItems"], len(live))
        self.assertEqual(self._lastmod(QUESTIONS[2][0]), max(c["fetched_at"][:10] for c in courses))

    def test_c_vs_b_difference(self):
        C, Bv = at("UEFA C"), at("UEFA B")
        co, bo = len([c for c in C if is_live(c)]), len([c for c in Bv if is_live(c)])
        s = soup(QUESTIONS[3][0])
        summary = norm(s.select_one("#summary").get_text())
        self.assertIn(f"{len(C)} UEFA C football coaching courses and {len(Bv)} UEFA B football coaching courses.", summary)
        self.assertIn(f"{co} UEFA C and {bo} UEFA B courses are open for applications or booking.", summary)
        self.assertIn(f"are {and_list(price_range(C))} for UEFA C and {and_list(price_range(Bv))} for UEFA B", summary)
        self.assertIn("does not state entry rules, required hours or experience.", summary)
        self.assertEqual(int(s.select_one('tr[data-metric="tracked"] td[data-level="UEFA C"]').get_text()), len(C))
        self.assertEqual(int(s.select_one('tr[data-metric="tracked"] td[data-level="UEFA B"]').get_text()), len(Bv))
        self.assertEqual(int(s.select_one('tr[data-metric="open"] td[data-level="UEFA C"]').get_text()), co)
        self.assertEqual(int(s.select_one('tr[data-metric="open"] td[data-level="UEFA B"]').get_text()), bo)
        length = s.select_one('tr[data-metric="length"]').find_all("td")
        self.assertIn(f"{both_dates(C)} of {len(C)} courses list both dates", length[0].get_text())
        self.assertIn(f"{both_dates(Bv)} of {len(Bv)} courses list both dates", length[1].get_text())
        fees = s.select_one('tr[data-metric="fees"]').find_all("td")
        self.assertIn(f"{len(priced(C))} of {len(C)} list a price", fees[0].get_text())
        self.assertIn(f"{len(priced(Bv))} of {len(Bv)} list a price", fees[1].get_text())
        self.assertEqual(of_type(s, "ItemList")[0]["numberOfItems"], len(C) + len(Bv))
        self.assertEqual(self._lastmod(QUESTIONS[3][0]), max(c["fetched_at"][:10] for c in C + Bv))

    def test_open_courses_with_deadlines(self):
        live = [c for c in COURSES if is_live(c)]
        dated = sorted([c for c in live if c.get("deadline")], key=lambda c: (c["deadline"], c["id"]))
        s = soup(QUESTIONS[4][0])
        summary = norm(s.select_one("#summary").get_text())
        self.assertIn(f"{len(live)} football coaching courses in Europe are open for applications or booking on CoachBadge, and {len(dated)} of them state an application deadline.", summary)
        self.assertIn(f"The other {len(live) - len(dated)} open courses do not state a deadline.", summary)
        self.assertIn(f"within {CLOSING_DAYS} days.", summary)
        if dated:
            d = dated[0]
            self.assertIn(f"The earliest deadline is {fdate(d['deadline'])} ({d['provider']}, {d['country']}).", summary)
        ids = [tr["data-id"] for tr in s.select("#deadlines tbody tr")]
        self.assertEqual(ids, [c["id"] for c in dated])
        self.assertEqual(of_type(s, "ItemList")[0]["numberOfItems"], len(dated))
        self.assertEqual(self._lastmod(QUESTIONS[4][0]), max(c["fetched_at"][:10] for c in live))

    def test_uefa_a_deadlines(self):
        courses = at("UEFA A")
        stated = sorted([c for c in courses if c.get("deadline")], key=lambda c: (c["deadline"], c["id"]))
        in_2027 = [c for c in stated if c["deadline"].startswith("2027")]
        elite = at(ELITE)
        elite_stated = [c for c in elite if c.get("deadline")]
        elite_2027 = [c for c in elite_stated if c["deadline"].startswith("2027")]
        word = "deadline" if len(stated) == 1 else "deadlines"
        def in_2027_phrase(n):
            return "1 deadline falls in 2027" if n == 1 else f"{n} deadlines fall in 2027"
        s = soup(QUESTIONS[5][0])
        summary = norm(s.select_one("#summary").get_text())
        self.assertIn(f"{len(courses)} UEFA A licence courses and {len(stated)} stated application {word}, and {in_2027_phrase(len(in_2027))}.", summary)
        for c in stated:
            self.assertIn(fdate(c["deadline"]), summary)
            self.assertIn(c["provider"], summary)
            self.assertIn(LABEL[display(c)], summary)
        ey_state = "states" if len(elite_stated) == 1 else "state"
        self.assertIn(f"{len(elite)} UEFA Elite Youth A courses, of which {len(elite_stated)} {ey_state} an application deadline, and {in_2027_phrase(len(elite_2027))}.", summary)
        if "Wales" not in {c["country"] for c in COURSES}:
            self.assertIn("No course in this data is from Wales.", summary)
        for c in courses:
            row = s.select_one(f'#a-courses tr[data-id="{c["id"]}"]')
            want = fdate(c["deadline"]) if c.get("deadline") else "Not stated"
            self.assertEqual(row.find_all("td")[0].get_text(strip=True), want)
            self.assertEqual(row.find_all("a")[0]["href"], c["source_url"])
        for c in elite:
            row = s.select_one(f'#elite-courses tr[data-id="{c["id"]}"]')
            want = fdate(c["deadline"]) if c.get("deadline") else "Not stated"
            self.assertEqual(row.find_all("td")[0].get_text(strip=True), want)
        counts = sorted(il["numberOfItems"] for il in of_type(s, "ItemList"))
        self.assertEqual(counts, sorted([len(courses), len(elite)]))
        self.assertEqual(self._lastmod(QUESTIONS[5][0]), max(c["fetched_at"][:10] for c in courses + elite))

    def test_sweden_2027_how_to_apply(self):
        courses = sorted(sweden_b_2027(), key=lambda c: (c.get("deadline") or "9999", c["id"]))
        live = [c for c in courses if is_live(c)]
        s = soup(QUESTIONS[6][0])
        summary = norm(s.select_one("#summary").get_text())
        self.assertIn(f"lists {len(courses)} UEFA B coaching courses in Sweden with 2027 in the start date, the title or the deadline, and {len(live)} of them are open for applications or booking.", summary)
        if courses and courses[0].get("deadline"):
            d = courses[0]
            self.assertIn(f"The earliest deadline is {fdate(d['deadline'])} ({d['provider']}).", summary)
        groups = {}
        for c in priced(courses):
            groups[(amount_of(c), c["price"]["currency"])] = groups.get((amount_of(c), c["price"]["currency"]), 0) + 1
        parts = [f"{money(a, cur)} ({counted(n, 'course')})" for (a, cur), n in sorted(groups.items())]
        self.assertIn(f"Listed fees are {and_list(parts)}.", summary)
        faq = {q["name"]: q["acceptedAnswer"]["text"] for q in of_type(s, "FAQPage")[0]["mainEntity"]}
        how = faq["How do you apply?"]
        for c in courses:
            self.assertIn(for_copy(c["provider"]), how)
            self.assertIn(for_copy(c["title"]), how)
            self.assertIn(for_copy(c.get("application_window") or "") or "see the provider page", how)
            if c.get("deadline"):
                self.assertIn(fdate(c["deadline"]), how)
            row = s.select_one(f'#how-to-apply tr[data-id="{c["id"]}"]')
            self.assertEqual(row.find_all("a")[0]["href"], c["source_url"])
        self.assertEqual(of_type(s, "ItemList")[0]["numberOfItems"], len(courses))
        self.assertEqual(self._lastmod(QUESTIONS[6][0]), max(c["fetched_at"][:10] for c in courses))

    def test_course_jsonld_uses_real_prices(self):
        for path, _h in QUESTIONS:
            s = soup(path)
            for il in of_type(s, "ItemList"):
                self.assertEqual(il["numberOfItems"], len(il["itemListElement"]))
                self.assertEqual([i["position"] for i in il["itemListElement"]], list(range(1, il["numberOfItems"] + 1)))
                for li in il["itemListElement"]:
                    item = li.get("item")
                    if not item or item.get("@type") != "Course":
                        continue
                    matches = [c for c in COURSES if c["title"] == item["name"] and c["source_url"] == item["url"]]
                    self.assertTrue(matches, item["name"])
                    if "offers" in item:
                        self.assertTrue(any(amount_of(c) == item["offers"]["price"] and c["price"]["currency"] == item["offers"]["priceCurrency"] for c in matches))
                    else:
                        self.assertTrue(any(amount_of(c) is None for c in matches))

    def test_answers_index(self):
        s = soup("answers.html")
        summary = norm(s.select_one("#summary").get_text())
        self.assertIn(f"As of {GEN}, CoachBadge publishes {len(QUESTIONS)} short answers", summary)
        self.assertEqual([(a["href"], a.get_text()) for a in s.select("ul.answers a")], QUESTIONS)
        il, = of_type(s, "ItemList")
        self.assertEqual(il["numberOfItems"], len(QUESTIONS))
        self.assertEqual([x["url"] for x in il["itemListElement"]], [BASE + p for p, _h in QUESTIONS])
        self.assertEqual(of_type(s, "FAQPage"), [])
        sm = dict(re.findall(r"<loc>(.*?)</loc><lastmod>(.*?)</lastmod>", open(os.path.join(DIST, "sitemap.xml")).read()))
        self.assertEqual(sm[BASE + "answers.html"], GENERATED)
        self.assertIn(BASE + "answers.html", open(os.path.join(DIST, "llms.txt")).read())
        self.assertIn(BASE + "answers.html", open(os.path.join(DIST, "llms-full.txt")).read())

    def _lastmod(self, path):
        sm = dict(re.findall(r"<loc>(.*?)</loc><lastmod>(.*?)</lastmod>", open(os.path.join(DIST, "sitemap.xml")).read()))
        return sm[BASE + path]


if __name__ == "__main__":
    unittest.main()
