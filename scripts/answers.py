"""Question pages for answer engines.

Every count, fee and date is computed from data/courses.json. Diploma lines come from
data/diplomas.yaml. No figure in the copy is typed in by hand.

Eight pages, one per question: pathway order, UEFA C fees by country, UEFA B courses
open in Europe, UEFA C vs UEFA B, open courses that state a deadline, UEFA A deadlines,
UEFA B in Sweden for 2027, and the lowest listed UEFA C fee.
"""
import re

# (path, h1). The h1 is the question wording, with a capital first letter where the
# question was typed in lower case.
SPECS = [
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
PATHWAY = ["UEFA C", "UEFA B", "UEFA A", "UEFA Pro"]
ELITE = "UEFA Elite Youth A"
FULL_MONTHS = "January February March April May June July August September October November December".split()
_BANNED = re.compile(r"official|mandatory|primelogic|stathopoulos", re.I)
_DASH = re.compile(r"[\u2013\u2014]")


def for_copy(s):
    """Provider text placed in a sentence or table we write. A dash in the source becomes a hyphen."""
    return re.sub(r"\s+", " ", (s or "").replace("\u2013", " - ").replace("\u2014", " - ")).strip()


def plain_ok(s, where):
    bad = _DASH.search(s) or _BANNED.search(s)
    if bad:
        raise SystemExit(f"new copy failed the wording check ({where}): {bad.group(0)!r} in {s[:220]}")


def meta_desc(lead):
    s = re.split(r"(?<=[.])\s+", lead.strip())[0]
    if len(s) > 300:
        s = s[:297].rsplit(" ", 1)[0]
    if not 20 <= len(s) <= 300:
        raise SystemExit(f"description length {len(s)}: {s}")
    return s


def lists(n, rest):
    return f"{n} {'lists' if n == 1 else 'list'} {rest}"


def deadlines_in_2027(n):
    """Exact count without the phrase '0 of', which the empty-country check treats as a missing list."""
    if n == 1:
        return "1 deadline falls in 2027"
    return f"{n} deadlines fall in 2027"


def by_deadline(c):
    return (c.get("deadline") or "9999", c["id"])


def amount_of(c):
    return (c.get("price") or {}).get("amount")


def priced(cs):
    return [c for c in cs if amount_of(c) is not None]


def at(B, level):
    return [c for c in B.COURSES if c["level"] == level]


def month_year(B):
    g = B.DATA["generated"]
    return f"{FULL_MONTHS[int(g[5:7]) - 1]} {g[:4]}"


def lastmod_of(B, cs):
    if not cs:
        return B.DATA["generated"][:10]
    return max(c["fetched_at"][:10] for c in cs)


def join_lead(*parts):
    return " ".join(p.strip() for p in parts if p and p.strip())


def lowest_phrase(B, cs):
    """Lowest price amount. Same amount in more than one currency is listed once per currency."""
    fees = priced(cs)
    if not fees:
        return ""
    amount = min(amount_of(c) for c in fees)
    winners = [c for c in fees if amount_of(c) == amount]
    bits = []
    for cur in sorted({c["price"]["currency"] for c in winners}):
        countries = sorted({c["country"] for c in winners if c["price"]["currency"] == cur})
        bits.append(f"{B.fprice({'amount': amount, 'currency': cur})} in {B.and_list(countries)}")
    return B.and_list(bits)


def per_currency_phrase(B, cs):
    best = {}
    for c in priced(cs):
        cur, amt = c["price"]["currency"], amount_of(c)
        rec = best.get(cur)
        if rec is None or amt < rec["amount"]:
            best[cur] = {"amount": amt, "countries": {c["country"]}}
        elif amt == rec["amount"]:
            rec["countries"].add(c["country"])
    bits = [f"{B.fprice({'amount': best[cur]['amount'], 'currency': cur})} in {B.and_list(sorted(best[cur]['countries']))}"
            for cur in sorted(best)]
    return B.and_list(bits)


def fee_notes(cs):
    return sorted({for_copy(c["price"].get("note") or "") for c in priced(cs) if c["price"].get("note")})


def fee_sentence(B, cs):
    groups = {}
    for c in priced(cs):
        k = (amount_of(c), c["price"]["currency"])
        groups[k] = groups.get(k, 0) + 1
    if not groups:
        return "None of these courses lists a fee."
    parts = [f"{B.fprice({'amount': a, 'currency': cur})} ({B.counted(n, 'course')})" for (a, cur), n in sorted(groups.items())]
    return f"Listed fees are {B.and_list(parts)}."


def open_clause_days(B):
    return f"Open includes Closing soon: an open course whose deadline falls within {B.CLOSING_DAYS} days."


def src(B, url):
    return f'<a href="{B.e(url)}" rel="nofollow noopener">Source</a>'


def info_table(table_id, headers, rows):
    th = "".join(f"<th>{h}</th>" for h in headers)
    return (f'<div style="overflow-x:auto"><table class="info" id="{table_id}"><thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def fee_table(B, cs):
    grouped = {}
    for c in priced(cs):
        p = c["price"]
        k = (c["country"], c["provider"], p["amount"], p["currency"], p.get("note") or "")
        r = grouped.setdefault(k, {"n": 0, "urls": [], "checked": c["fetched_at"][:10]})
        r["n"] += 1
        if c["source_url"] not in r["urls"]:
            r["urls"].append(c["source_url"])
        r["checked"] = max(r["checked"], c["fetched_at"][:10])
    rows = []
    for (country, provider, amount, cur, note), v in sorted(grouped.items(), key=lambda kv: (kv[0][0], kv[0][2], kv[0][1])):
        note_cell = B.e(for_copy(note)) if note else "Not stated"
        links = " ".join(src(B, u) for u in v["urls"])
        fee = B.fprice({"amount": amount, "currency": cur})
        rows.append(
            f'<tr data-country="{B.e(country)}" data-amount="{amount}" data-currency="{B.e(cur)}" data-courses="{v["n"]}">'
            f"<td>{B.e(country)}</td><td>{B.e(provider)}</td><td><strong>{B.e(fee)}</strong></td><td>{note_cell}</td>"
            f"<td>{v['n']}</td><td>{links}</td><td>{B.e(B.fdate(v['checked']))}</td></tr>")
    return info_table("fees", ["Country", "Provider", "Fee", "Provider note", "Courses", "Source", "Checked"], rows)


def unpriced_table(B, cs):
    rows = []
    for c in sorted(cs, key=lambda c: (c["country"], c["provider"], c["id"])):
        note = for_copy(c.get("price_note") or "")
        rows.append(
            f'<tr data-id="{B.e(c["id"])}"><td>{B.e(c["country"])}</td><td>{B.e(c["provider"])}</td>'
            f'<td>{B.e(for_copy(c["title"]))}</td><td>{B.e(note) if note else "Not listed"}</td><td>{src(B, c["source_url"])}</td></tr>')
    return info_table("no-fee", ["Country", "Provider", "Course", "What the page says", "Source"], rows)


def course_table(B, table_id, cs):
    rows = []
    for c in cs:
        dl = B.fdate(c["deadline"]) if c.get("deadline") else "Not stated"
        window = for_copy(c.get("application_window") or "") or "Not stated"
        start = B.fdate(c["start_date"]) if c.get("start_date") else "Not stated"
        fee = B.fprice(c.get("price")) or "Not listed"
        rows.append(
            f'<tr data-id="{B.e(c["id"])}"><td>{B.e(B.STATUS_LABEL[c["display_status"]])}</td><td>{B.e(c["country"])}</td>'
            f'<td>{B.e(for_copy(c["title"]))}</td><td>{B.e(c["provider"])}</td><td>{B.e(dl)}</td><td>{B.e(window)}</td>'
            f'<td>{B.e(start)}</td><td>{B.e(fee)}</td><td>{src(B, c["source_url"])}</td></tr>')
    return info_table(table_id, ["Status", "Country", "Course", "Provider", "Deadline", "How to apply", "Starts", "Fee", "Source"], rows)


def deadline_table(B, table_id, cs):
    rows = []
    for c in sorted(cs, key=by_deadline):
        dl = B.fdate(c["deadline"]) if c.get("deadline") else "Not stated"
        rows.append(
            f'<tr data-id="{B.e(c["id"])}"><td>{B.e(dl)}</td><td>{B.e(for_copy(c["title"]))}</td><td>{B.e(c["provider"])}</td>'
            f'<td>{B.e(c["country"])}</td><td>{B.e(B.STATUS_LABEL[c["display_status"]])}</td>'
            f'<td>{B.e(B.fdate(c["fetched_at"][:10]))}</td><td>{src(B, c["source_url"])}</td></tr>')
    return info_table(table_id, ["Deadline", "Course", "Provider", "Country", "Status", "Checked", "Source"], rows)


def related(B, self_path):
    items = [f'<li><a href="{{R}}{path}">{B.e(h1)}</a></li>' for path, h1 in SPECS if path != self_path]
    return '<h2><span class="bar"></span>Related answers</h2><ul class="answers">' + "".join(items) + "</ul>"


def emit(B, path, h1, lead, after, faq, item_lists, lastmod):
    plain_ok(h1, path)
    plain_ok(lead, path)
    if "\n" in lead:
        raise SystemExit(f"newline in lead {path}")
    for q, a in faq:
        plain_ok(q, path)
        plain_ok(a, path)
    desc = meta_desc(lead)
    pairs = [(q, B.e(a)) for q, a in faq]
    rel = "../" * path.count("/")
    ld = []
    for name, cs in item_lists:
        if cs:
            ld.append(B.item_list(name, B.BASE + path, cs))
    ld.append({"@context": "https://schema.org", "@type": "Article", "headline": h1, "description": desc,
               "url": B.BASE + path, "dateModified": B.DATA["generated"][:10], "inLanguage": "en",
               "author": {"@type": "Organization", "name": B.BRAND, "url": B.BASE},
               "publisher": {"@type": "Organization", "name": B.BRAND, "url": B.BASE},
               "isBasedOn": B.BASE + "data/courses.json"})
    ld.append({"@context": "https://schema.org", "@type": "Dataset", "name": h1, "description": lead,
               "url": B.BASE + path, "dateModified": B.DATA["generated"][:10], "inLanguage": "en",
               "creator": {"@type": "Organization", "name": B.BRAND, "url": B.BASE},
               "isBasedOn": B.BASE + "data/courses.json", "license": B.BASE + "terms.html"})
    ld.append(B.seo.faq_ld(pairs))
    body = f"""<main><div class="wrap"><h1>{B.e(h1)}</h1>
<p class="answer" id="summary">{B.e(lead)}</p>
{B.updated_line()}
{B.seo.faq_html(pairs)}
{after}
{related(B, path)}
<p class="small">Data last checked {B.e(B.GEN)}. Course details come from each provider's own pages and can change at any time; always confirm with the provider before you apply. <a href="{{R}}methodology.html">How we gather the data</a>.</p>
{B.signup_form("subscribe-mid")}
{B.resources_box(rel)}
</div></main>"""
    B.page(path, h1, desc, body, ld, crumbs=[(B.BRAND, ""), ("Answers", "answers.html"), (h1, path)], lastmod=lastmod)
    B.ANSWER_PAGES.append((path, h1, lead))


def page_pathway(B):
    path, h1 = SPECS[0]
    counts = [(lv, at(B, lv)) for lv in PATHWAY]
    bits = [f"{len(cs)} {lv} courses" for lv, cs in counts]
    elite = at(B, ELITE)
    lead = join_lead(
        f"As of {B.GEN}, {B.BRAND} lists the UEFA football coaching licence pathway in this order: UEFA C, then UEFA B, then UEFA A, then UEFA Pro.",
        f"This data has {B.and_list(bits)}.",
        f"UEFA Elite Youth A is a separate level in this data ({len(elite)} courses). {B.BRAND} does not set entry rules, required hours or experience between these levels.")
    open_bits = [f"{lv}: {len([c for c in cs if B.is_live(c)])} open of {len(cs)}" for lv, cs in counts]
    faq = [
        (h1, lead),
        ("How many of those courses are open for applications?", f"As of {B.GEN}, {B.and_list(open_bits)}."),
        (f"Does {B.BRAND} set the pathway from UEFA C to UEFA Pro?",
         f"No. {B.CFG['disclaimer']} {B.BRAND} does not set entry rules, required hours or experience between these levels."),
    ]
    rows = []
    for i, (lv, cs) in enumerate(counts, 1):
        live = [c for c in cs if B.is_live(c)]
        countries = B.and_list(sorted({c["country"] for c in cs}))
        rows.append(
            f'<tr data-level="{B.e(lv)}" data-tracked="{len(cs)}" data-open="{len(live)}"><td>{i}</td>'
            f'<td><a href="{{R}}level/{B.slug(lv)}.html">{B.e(lv)}</a></td><td>{len(cs)}</td><td>{len(live)}</td>'
            f'<td>{B.e(countries)}</td></tr>')
    live_e = [c for c in elite if B.is_live(c)]
    rows.append(
        f'<tr data-level="{B.e(ELITE)}" data-tracked="{len(elite)}" data-open="{len(live_e)}"><td>Separate</td>'
        f'<td><a href="{{R}}level/{B.slug(ELITE)}.html">{B.e(ELITE)}</a></td><td>{len(elite)}</td><td>{len(live_e)}</td>'
        f'<td>{B.e(B.and_list(sorted({c["country"] for c in elite})))}</td></tr>')
    others = [lv for lv in B.LEVELS if lv not in PATHWAY and lv != ELITE]
    other_p = ""
    if others:
        other_p = "<p>Other labels in this data: " + B.e(B.and_list([f"{lv} ({len(at(B, lv))} courses)" for lv in others])) + ".</p>"
    dips = []
    for _ct, info in sorted((B.DIPLOMAS or {}).items()):
        for d in info.get("diplomas") or []:
            dips.append(f'<li><strong>{B.e(d["short"])}</strong> ({B.e(d["name"])}) is stated as {B.e(d["uefa"])}. '
                        f'<a href="{B.e(d["url"])}" rel="nofollow noopener">Source</a></li>')
    dip_block = ""
    if dips:
        dip_block = ('<h2><span class="bar"></span>National diplomas and the level a federation states</h2>'
                     '<p>These equivalences are quoted from the federation pages in the data. They are not an entry order, and they are not courses.</p>'
                     f'<ul id="diplomas">{"".join(dips)}</ul>')
    shown = []
    for lv in PATHWAY + [ELITE]:
        shown.extend(at(B, lv))
    after = f"""<h2><span class="bar"></span>Levels in this order</h2>
{info_table("pathway", ["Order", "Level", "Courses tracked", "Open now", "Countries"], rows)}
{other_p}
{dip_block}"""
    emit(B, path, h1, lead, after, faq, [(h1, shown)], lastmod_of(B, shown))


def fee_facts(B):
    all_c = at(B, "UEFA C")
    fees = priced(all_c)
    missing = [c for c in all_c if amount_of(c) is None]
    countries = sorted({c["country"] for c in fees})
    return all_c, fees, missing, countries


def fee_block(B, all_c, missing):
    return f"""<h2><span class="bar"></span>Fees by country</h2>
{fee_table(B, all_c)}
<p class="small">The fee column is the price amount. A provider note is repeated beside it and is not a second fee amount. Amounts are not converted between currencies.</p>
<h2><span class="bar"></span>UEFA C courses with no fee amount</h2>
{unpriced_table(B, missing)}
<p>See also <a href="{{R}}level/uefa-c.html">UEFA C courses</a>.</p>"""


def page_cost(B):
    path, h1 = SPECS[1]
    all_c, fees, missing, countries = fee_facts(B)
    phrase = lowest_phrase(B, all_c)
    lead = join_lead(
        f"As of {B.GEN}, {len(fees)} of the {len(all_c)} UEFA C courses {B.BRAND} tracks list a fee, in {B.counted(len(countries), 'country', 'countries')}: {B.and_list(countries)}.",
        f"The lowest listed fee is {phrase}.",
        f"{len(missing)} UEFA C courses list no fee amount.",
        "Each fee below is the price amount on the provider's page, in that provider's currency, with the source link. Amounts are not converted.")
    faq = [
        (h1, lead),
        ("Which countries have a listed UEFA C fee?", f"As of {B.GEN}, the countries are {B.and_list(countries)}."),
        ("Are the fees converted into one currency?", "No. Each fee stays in the provider's currency. Amounts are not converted."),
    ]
    emit(B, path, h1, lead, fee_block(B, all_c, missing), faq, [(h1, all_c)], lastmod_of(B, all_c))


def page_b_open(B):
    path, h1 = SPECS[2]
    courses = at(B, "UEFA B")
    live = sorted([c for c in courses if B.is_live(c)], key=by_deadline)
    d2026 = [c for c in live if (c.get("deadline") or "").startswith("2026")]
    later = [c for c in live if c.get("deadline") and not c["deadline"].startswith("2026")]
    none = [c for c in live if not c.get("deadline")]
    s1 = f"As of {B.GEN}, {len(live)} of the {len(courses)} UEFA B football coaching courses {B.BRAND} tracks are open for applications or booking in Europe."
    if live:
        s2 = (f"Of those {len(live)}, {lists(len(d2026), 'an application deadline in 2026')}, "
              f"{lists(len(later), 'a deadline after 2026')}, and {lists(len(none), 'no deadline')}.")
        s3 = f"The open courses are in {B.and_list(sorted({c['country'] for c in live}))}."
    else:
        s2, s3 = "No UEFA B course is open for applications in this data.", ""
    lead = join_lead(s1, s2, s3, open_clause_days(B))
    bits = []
    for c in live:
        dl = B.fdate(c["deadline"]) if c.get("deadline") else "no deadline stated"
        bits.append(f"{for_copy(c['provider'])}, {c['country']}, {dl}")
    who = "The open UEFA B courses are: " + "; ".join(bits) + "." if bits else "No UEFA B course is open for applications in this data."
    faq = [
        (h1, lead),
        ("Which UEFA B courses are open for applications?", who),
        ("How many open UEFA B courses list a deadline in 2026?",
         f"As of {B.GEN}, {lists(len(d2026), 'an application deadline in 2026')}."),
    ]
    after = f"""<h2><span class="bar"></span>Open UEFA B courses</h2>
{course_table(B, "open-courses", live) if live else "<p>No UEFA B course is open for applications in this data.</p>"}
<p>See also <a href="{{R}}level/uefa-b.html">UEFA B courses</a>.</p>"""
    emit(B, path, h1, lead, after, faq, [(h1, live)], lastmod_of(B, courses))


def page_c_vs_b(B):
    path, h1 = SPECS[3]
    C, Bv = at(B, "UEFA C"), at(B, "UEFA B")
    co, bo = len([c for c in C if B.is_live(c)]), len([c for c in Bv if B.is_live(c)])
    pc = B.and_list(B.price_range(C)) or "not listed"
    pb = B.and_list(B.price_range(Bv)) or "not listed"
    lead = join_lead(
        f"As of {B.GEN}, {B.BRAND} tracks {len(C)} UEFA C football coaching courses and {len(Bv)} UEFA B football coaching courses.",
        f"{co} UEFA C and {bo} UEFA B courses are open for applications or booking.",
        f"Listed fees, where a provider gives one, are {pc} for UEFA C and {pb} for UEFA B, and this page does not state entry rules, required hours or experience.")

    def length_cell(cs):
        text, n = B.g_weeks(cs)
        return f"{B.e(text)} ({n} of {len(cs)} courses list both dates)"

    def price_cell(cs):
        pr = B.and_list(B.price_range(cs)) or "Not listed"
        return f"{B.e(pr)} ({len(priced(cs))} of {len(cs)} list a price)"

    rows = [
        f'<tr data-metric="tracked"><th scope="row">Courses tracked</th><td data-level="UEFA C">{len(C)}</td><td data-level="UEFA B">{len(Bv)}</td></tr>',
        f'<tr data-metric="open"><th scope="row">Open for applications or booking</th><td data-level="UEFA C">{co}</td><td data-level="UEFA B">{bo}</td></tr>',
        f'<tr data-metric="countries"><th scope="row">Countries</th><td>{B.e(B.and_list(sorted({c["country"] for c in C})))}</td><td>{B.e(B.and_list(sorted({c["country"] for c in Bv})))}</td></tr>',
        f'<tr data-metric="providers"><th scope="row">Providers</th><td>{len({c["provider"] for c in C})}</td><td>{len({c["provider"] for c in Bv})}</td></tr>',
        f'<tr data-metric="fees"><th scope="row">Listed fees</th><td>{price_cell(C)}</td><td>{price_cell(Bv)}</td></tr>',
        f'<tr data-metric="format"><th scope="row">Format</th><td>{B.e(B.g_formats(C))}</td><td>{B.e(B.g_formats(Bv))}</td></tr>',
        f'<tr data-metric="length"><th scope="row">Length, start to end date</th><td>{length_cell(C)}</td><td>{length_cell(Bv)}</td></tr>',
    ]
    faq = [
        (h1, lead),
        ("How many UEFA C and UEFA B courses are open?",
         f"As of {B.GEN}, {co} UEFA C and {bo} UEFA B courses are open for applications or booking."),
        ("Does this page state entry rules for UEFA C or UEFA B?",
         "No. This page does not state entry rules, required hours or experience."),
    ]
    after = f"""<h2><span class="bar"></span>What this data can compare</h2>
<div style="overflow-x:auto"><table class="info" id="compare"><thead><tr><th></th><th>UEFA C</th><th>UEFA B</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<p class="small">Fees stay in the provider's currency. Amounts are not converted.</p>
<p>See also <a href="{{R}}level/uefa-c.html">UEFA C courses</a>, <a href="{{R}}level/uefa-b.html">UEFA B courses</a> and <a href="{{R}}cost/uefa-c.html">How much does a UEFA C licence cost in different countries</a>.</p>"""
    emit(B, path, h1, lead, after, faq, [(h1, C + Bv)], lastmod_of(B, C + Bv))


def page_open_deadlines(B):
    path, h1 = SPECS[4]
    live = [c for c in B.COURSES if B.is_live(c)]
    dated = sorted([c for c in live if c.get("deadline")], key=by_deadline)
    rest = len(live) - len(dated)
    s1 = (f"As of {B.GEN}, {len(live)} football coaching courses in Europe are open for applications or booking on {B.BRAND}, "
          f"and {len(dated)} of them state an application deadline.")
    if dated:
        d = dated[0]
        s2 = f"The earliest deadline is {B.fdate(d['deadline'])} ({d['provider']}, {d['country']})."
    else:
        s2 = "None of the open courses states an application deadline."
    s3 = f"The other {rest} open courses do not state a deadline."
    lead = join_lead(s1, s2, s3, open_clause_days(B))
    faq = [
        (h1, lead),
        ("How many open courses state an application deadline?",
         f"{len(dated)} of the {len(live)} open courses state an application deadline, as of {B.GEN}."),
        ("What is the earliest application deadline among open courses?", s2),
    ]
    after = f"""<h2><span class="bar"></span>Open courses that state a deadline</h2>
{course_table(B, "deadlines", dated) if dated else "<p>No open course states an application deadline.</p>"}
<p>Open courses with no deadline are on the <a href="{{HOME}}">course board</a>.</p>"""
    emit(B, path, h1, lead, after, faq, [(h1, dated)], lastmod_of(B, live))


def page_a_deadlines(B):
    path, h1 = SPECS[5]
    courses = at(B, "UEFA A")
    stated = sorted([c for c in courses if c.get("deadline")], key=by_deadline)
    in_2027 = [c for c in stated if c["deadline"].startswith("2027")]
    elite = at(B, ELITE)
    elite_stated = [c for c in elite if c.get("deadline")]
    elite_2027 = [c for c in elite_stated if c["deadline"].startswith("2027")]
    word = "deadline" if len(stated) == 1 else "deadlines"
    ey_state = "states" if len(elite_stated) == 1 else "state"
    parts = [f"As of {B.GEN}, {B.BRAND} tracks {len(courses)} UEFA A licence courses and {len(stated)} stated application {word}, and {deadlines_in_2027(len(in_2027))}."]
    if stated:
        listed = "; ".join(
            f"{B.fdate(c['deadline'])} ({for_copy(c['title'])}, {c['provider']}, {c['country']}, {B.STATUS_LABEL[c['display_status']]})"
            for c in stated)
        parts.append(f"The stated UEFA A deadlines are {listed}.")
    else:
        parts.append("No UEFA A course in this data states an application deadline.")
    parts.append(
        f"Separately, this data has {len(elite)} UEFA Elite Youth A courses, of which {len(elite_stated)} {ey_state} an application deadline, and {deadlines_in_2027(len(elite_2027))}.")
    if "Wales" not in {c["country"] for c in B.COURSES}:
        parts.append("No course in this data is from Wales.")
    lead = join_lead(*parts)
    y_word = "deadline" if len(in_2027) == 1 else "deadlines"
    y_verb = "falls" if len(in_2027) == 1 else "fall"
    state = "states" if len(stated) == 1 else "state"
    faq = [
        (h1, lead),
        ("How many UEFA A application deadlines fall in 2027?",
         f"As of {B.GEN}, {len(in_2027)} stated UEFA A application {y_word} {y_verb} in 2027. {len(courses)} UEFA A courses are tracked and {len(stated)} {state} a deadline."),
        ("What UEFA A application deadlines does this data list?", parts[1]),
    ]
    after = f"""<h2><span class="bar"></span>Every UEFA A course, with the application deadline when the page states one</h2>
{deadline_table(B, "a-courses", courses)}
<h2><span class="bar"></span>UEFA Elite Youth A courses, with the application deadline when the page states one</h2>
{deadline_table(B, "elite-courses", elite)}
<p>See also <a href="{{R}}level/uefa-a.html">UEFA A courses</a> and <a href="{{R}}level/uefa-a-2027.html">UEFA A courses with 2027 in a date or title</a>.</p>"""
    emit(B, path, h1, lead, after, faq,
         [(h1, courses), ("UEFA Elite Youth A courses in this data", elite)],
         lastmod_of(B, courses + elite))


def sweden_b_2027(B):
    out = []
    for c in B.COURSES:
        if c["country"] != "Sweden" or c["level"] != "UEFA B":
            continue
        if ((c.get("start_date") or "").startswith("2027") or "2027" in (c.get("title") or "")
                or (c.get("deadline") or "").startswith("2027")):
            out.append(c)
    return sorted(out, key=by_deadline)


def page_sweden(B):
    path, h1 = SPECS[6]
    courses = sweden_b_2027(B)
    live = [c for c in courses if B.is_live(c)]
    dated = [c for c in courses if c.get("deadline")]
    s1 = (f"As of {B.GEN}, {B.BRAND} lists {len(courses)} UEFA B coaching courses in Sweden with 2027 in the start date, the title or the deadline, "
          f"and {len(live)} of them are open for applications or booking.")
    if dated:
        d = dated[0]
        s2 = f"Apply on each provider's own page. The earliest deadline is {B.fdate(d['deadline'])} ({d['provider']})."
    else:
        s2 = "No course in this list states an application deadline. Apply on each provider's own page."
    lead = join_lead(s1, s2, fee_sentence(B, courses), open_clause_days(B))
    parts = []
    for c in courses:
        window = for_copy(c.get("application_window") or "") or "see the provider page"
        dl = B.fdate(c["deadline"]) if c.get("deadline") else "not stated"
        parts.append(f"{for_copy(c['provider'])} ({for_copy(c['title'])}): {window}. Deadline {dl}.")
    how = "Apply on the provider's page. " + " ".join(parts) if parts else "No Sweden UEFA B course with 2027 in the start date, the title or the deadline is in this data."
    faq = [
        (h1, lead),
        ("How many UEFA B courses in Sweden have 2027 in the start date, title or deadline?",
         f"As of {B.GEN}, {len(courses)}. {len(live)} of them are open for applications or booking."),
        ("How do you apply?", how),
    ]
    after = f"""<h2><span class="bar"></span>How to apply</h2>
{course_table(B, "how-to-apply", courses) if courses else "<p>No matching course is in this data.</p>"}
<p>See also <a href="{{R}}level/uefa-b-sweden.html">UEFA B courses in Sweden</a>.</p>"""
    emit(B, path, h1, lead, after, faq, [(h1, courses)], lastmod_of(B, courses))


def page_cheapest(B):
    path, h1 = SPECS[7]
    all_c, fees, missing, countries = fee_facts(B)
    winners = []
    if fees:
        low = min(amount_of(c) for c in fees)
        winners = [c for c in fees if amount_of(c) == low]
    phrase = lowest_phrase(B, all_c)
    notes = fee_notes(all_c)
    note_line = ("The notes on file are: " + "; ".join(notes) + ".") if notes else "No provider note is on file beside a fee amount."
    if phrase:
        providers = B.and_list(sorted({c["provider"] for c in winners}))
        lead = join_lead(
            f"In {B.BRAND}'s {month_year(B)} data, the lowest listed UEFA C fee is {phrase}.",
            f"That price amount is on {len(winners)} courses from {providers}, among {len(fees)} UEFA C courses that list a fee in {B.counted(len(countries), 'country', 'countries')} ({B.and_list(countries)}).",
            f"{len(missing)} UEFA C courses list no fee amount.",
            f"The lowest listed fee in each currency is {per_currency_phrase(B, all_c)}.",
            "Amounts are not converted between currencies. Provider notes are not used as the fee amount.",
            note_line)
    else:
        lead = f"In {B.BRAND}'s {month_year(B)} data, no UEFA C course lists a fee."
    faq = [
        (h1, lead),
        ("What is the lowest listed UEFA C fee in each currency?",
         f"The lowest listed fee in each currency is {per_currency_phrase(B, all_c)}." if phrase else lead),
        ("Are provider notes included in the lowest fee?",
         "No. The lowest fee uses the price amount only. " + note_line),
    ]
    emit(B, path, h1, lead, fee_block(B, all_c, missing), faq, [(h1, all_c)], lastmod_of(B, all_c))


def page_index(B):
    intro = (f"As of {B.GEN}, {B.BRAND} publishes {len(SPECS)} short answers on UEFA football coaching licences, deadlines and fees. "
             "Every count is taken from the course data.")
    plain_ok(intro, "answers.html")
    lis = "".join(f'<li><a href="{path}">{B.e(h1)}</a></li>' for path, h1 in SPECS)
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": "Football coaching course answers",
          "url": B.BASE + "answers.html", "numberOfItems": len(SPECS),
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": h1, "url": B.BASE + path}
                              for i, (path, h1) in enumerate(SPECS)]}
    body = f"""<main><div class="wrap"><h1>Football coaching course answers</h1>
<p class="answer" id="summary">{B.e(intro)}</p>
{B.updated_line()}
<ul class="answers">{lis}</ul>
</div></main>"""
    B.page("answers.html", "Football coaching course answers", intro, body, [ld],
           crumbs=[(B.BRAND, ""), ("Answers", "answers.html")], lastmod=B.DATA["generated"][:10])


def build_answers(B):
    B.ANSWER_PAGES.clear()
    page_pathway(B)
    page_cost(B)
    page_b_open(B)
    page_c_vs_b(B)
    page_open_deadlines(B)
    page_a_deadlines(B)
    page_sweden(B)
    page_cheapest(B)
    page_index(B)
