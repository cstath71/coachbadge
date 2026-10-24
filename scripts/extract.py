"""Build data/courses.json from cached official pages (parsers) + data/manual_courses.yaml.
Only fields printed on the source page are filled; everything else stays null.
Usage: python3 scripts/extract.py [--today YYYY-MM-DD]"""
import json, os, re, sys, datetime
import yaml
from bs4 import BeautifulSoup
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch import fetch, to_text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MONTHS = {m: i for i, m in enumerate(["january","february","march","april","may","june","july",
          "august","september","october","november","december"], 1)}

def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()

def en_date(s):
    m = re.search(r"(\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December) (\d{4})", s)
    if not m: return None
    return datetime.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()

# ---------- England FA: UEFA C course list ----------
FA_C = "https://learn.englandfootball.com/courses/football/uefa-c-licence"
def parse_fa_uefa_c(today):
    meta = fetch(FA_C)
    lines = [norm(l) for l in to_text(meta).split("\n") if l.strip()]
    page = norm(" ".join(lines))
    gate = "UEFA C Diploma 2026/27 season courses now available"
    if gate not in page:
        return [], "gate phrase missing"
    out, region = [], None
    i = 0
    while i < len(lines):
        l = lines[i]
        if re.fullmatch(r"[A-Z][A-Za-z ]+ Courses", l) and l != "Courses":
            region = l[:-len(" Courses")]
        if l == "Venue:" and i + 1 < len(lines):
            venue = lines[i + 1]
            block = []
            j = i + 2
            while j < len(lines) and lines[j] != "Book now" and lines[j] != "Venue:":
                block.append(lines[j]); j += 1
            booked = j < len(lines) and lines[j] == "Book now"
            fields = {}
            k = 0
            while k < len(block) - 1:
                if block[k].endswith(":"):
                    fields[block[k][:-1]] = block[k + 1]; k += 2
                else:
                    k += 1
            bc = fields.get("Broadcast Date", "")
            start = en_date(bc)
            m3 = fields.get("Module Three Dates", "")
            end = en_date(m3.split(" - ")[-1]) if m3 else None
            town = venue.split(",")[-2].strip() if venue.count(",") >= 2 else venue
            head = lines[i - 1] if i > 0 else ""
            code = re.search(r"\((UEFACD\d+)\)", head)
            m1 = en_date(fields.get("Module One Dates", "")) or ""
            slug = code.group(1).lower() if code else re.sub(r"[^a-z0-9]+", "-", (venue.split(",")[0][:30] + "-" + (start or "") + "-m" + m1).lower()).strip("-")
            status = "open" if booked else "unknown"
            basis = "Page: 'UEFA C Diploma 2026/27 season courses now available', course listed with 'Book now'"
            if start and start < today:
                status, basis = "closed", "online start (broadcast) date has passed"
            ev = [gate, venue]
            if bc: ev.append(bc)
            out.append({
                "id": f"eng-fa-uefa-c-{slug}"[:80], "sport": "football",
                "country": "Jersey" if "Jersey" in venue else ("Guernsey" if "Guernsey" in venue else "England"),
                "provider": "The Football Association (England)", "level": "UEFA C",
                "title": f"UEFA C Diploma – {venue.split(',')[0]}", "location": venue, "region": region,
                "language": "English", "format": "blended",
                "format_note": "Online broadcast session plus three face-to-face modules",
                "price": {"amount": 650, "currency": "GBP", "note": "£95 or £500 with FA funding for eligible coaches"},
                "deadline": None, "application_window": "First-come, first-served booking",
                "start_date": start, "end_date": end,
                "module_dates": {k: v for k, v in fields.items() if k.startswith("Module")},
                "status": status, "status_basis": basis, "source_url": FA_C,
                "fetched_at": meta["fetched_at"], "evidence": ev + ["£650", "Face-to-face & Online"],
            })
            i = j
        i += 1
    return out, None

# ---------- EPO Greece: UEFA C schools, phase 1 rows ----------
EPO = "https://www.epo.gr/el/uefa-c"
def gr_range(s):
    s = s.replace("/", ".")
    m = re.match(r"(\d{1,2})(?:\.(\d{1,2}))?-(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if not m: return None, None
    d1, mo1, d2, mo2, y = m.groups()
    mo1 = mo1 or mo2
    y1 = int(y) - (1 if int(mo1) > int(mo2) else 0)
    return datetime.date(y1, int(mo1), int(d1)).isoformat(), datetime.date(int(y), int(mo2), int(d2)).isoformat()

def parse_epo(today):
    meta = fetch(EPO)
    soup = BeautifulSoup(meta["body"], "html.parser")
    out = []
    for t in soup.find_all("table"):
        rows = [[c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])] for r in t.find_all("tr")]
        if not rows or rows[0][:2] != ["Διοργανώτρια ΕΠΣ", "Φάση"]:
            continue
        for r in rows[1:]:
            if len(r) < 5 or r[1] != "1η":
                continue
            start, end = gr_range(r[3])
            if not start or start < today:
                continue
            fa, place = r[0], r[4] or None
            out.append({
                "id": f"gre-epo-uefa-c-{start}-{sum(map(ord, fa)) % 1000}", "sport": "football", "country": "Greece",
                "provider": f"Hellenic Football Federation (EPO) with ΕΠΣ {fa}", "level": "UEFA C",
                "title": f"UEFA C school – ΕΠΣ {fa} (phase 1)", "location": place, "language": "Greek",
                "format": None, "format_note": "Three phases; this row is phase 1 (1η φάση)",
                "price": {"amount": 900, "currency": "EUR", "note": "total; €360 phase 1, €270 phase 2, €270 phase 3"},
                "deadline": None, "application_window": "Announced by EPO for each new school",
                "start_date": start, "end_date": end,
                "status": "unknown",
                "status_basis": "Schedule lists the school; the page does not state whether applications are open",
                "source_url": EPO, "fetched_at": meta["fetched_at"],
                "evidence": [fa, r[3], "€900"],
            })
    return out, None

# ---------- Saarland FA (DFB regional association) DFBnet course calendar ----------
SAAR = "https://www.dfbnet.org/vkal/mod_vkal/webflow.do?dmg_company=SFV&event=PLAN_NEW"
def de_range(s):
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(?:(\d{4}))?-(\d{2})\.(\d{2})\.(\d{4})", s)
    if m:
        d1, m1, y1, d2, m2, y2 = m.groups()
        return f"{y1 or y2}-{m1}-{d1}", f"{y2}-{m2}-{d2}"
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", s)
    if m:
        d, mo, y = m.groups(); return f"{y}-{mo}-{d}", f"{y}-{mo}-{d}"
    return None, None

def parse_saar(today):
    meta = fetch(SAAR)
    lines = [norm(l) for l in to_text(meta).split("\n") if l.strip()]
    out = []
    for i, l in enumerate(lines):
        if not re.fullmatch(r"\d{2}-Z-\d{5}", l) or i + 4 >= len(lines):
            continue
        date, name, until, status = lines[i + 1], lines[i + 2], lines[i + 3], lines[i + 4]
        if "Fortbildung" in name: continue
        if not re.search(r"\b[CB]-Lizenz\b", name): continue
        level = "UEFA C" if name.startswith("C-Lizenz") else "UEFA B"
        start, end = de_range(date)
        if not start or start < today: continue
        if status.startswith("noch") and "freie Plätze" in status:
            st, basis = "open", f"Online registration calendar shows '{status}'"
        elif status == "ausgebucht":
            st, basis = "full", "Calendar shows 'ausgebucht' (fully booked)"
        else:
            st, basis = "unknown", f"Calendar status '{status}'"
        out.append({
            "id": "ger-saarland-" + l.lower(), "sport": "football", "country": "Germany",
            "provider": "Saarländischer Fußballverband (DFB regional association)", "level": level,
            "title": name + (" (DFB licence, UEFA C level)" if level == "UEFA C" else " (DFB licence, UEFA B level)"),
            "location": "Saarland", "language": "German", "format": None,
            "price": None, "deadline": None if until == "unbekannt" else until,
            "application_window": "Online registration via DFBnet calendar",
            "start_date": start, "end_date": end if end != start else None,
            "status": st, "status_basis": basis, "source_url": SAAR,
            "fetched_at": meta["fetched_at"], "evidence": [l, name, status], "course_number": l,
        })
    return out, None

def main():
    today = datetime.date.today().isoformat()
    if "--today" in sys.argv: today = sys.argv[sys.argv.index("--today") + 1]
    courses, notes = [], {}
    for name, fn in [("fa_uefa_c", parse_fa_uefa_c), ("epo", parse_epo), ("saarland", parse_saar)]:
        rows, err = fn(today)
        notes[name] = {"rows": len(rows), "error": err}
        courses += rows
    manual = yaml.safe_load(open(os.path.join(ROOT, "data", "manual_courses.yaml")))
    courses += manual
    ids = [c["id"] for c in courses]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup: raise SystemExit(f"duplicate ids: {dup}")
    courses.sort(key=lambda c: (c["sport"], c["country"], c.get("start_date") or "9999", c["id"]))
    out = os.path.join(ROOT, "data", "courses.json")
    if "--out" in sys.argv: out = sys.argv[sys.argv.index("--out") + 1]
    json.dump({"generated": today, "count": len(courses), "parsers": notes, "courses": courses},
              open(out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(notes), len(courses))

if __name__ == "__main__":
    main()
