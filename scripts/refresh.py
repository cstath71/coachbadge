"""Weekly refresh. Restartable and review-only: it never edits data/courses.json or publishes anything.

  python3 scripts/refresh.py            # re-fetch every source not yet checked today, then report
  python3 scripts/refresh.py --force    # re-fetch everything again today
  python3 scripts/refresh.py --report   # only rebuild the report from saved state

Steps
 1. Collect every URL from data/sources.yaml and data/courses.json (source_url, extra_sources).
 2. Re-fetch politely (robots.txt, CoachBadgeBot user agent, 3 s per host). State is saved after
    every URL in data/source_state.json, so an interrupted run resumes where it stopped.
 3. Hash the page text; when the hash changed, keep a unified diff for review.
 4. Re-run the extractors into data/courses.candidate.json and diff against data/courses.json.
 5. Write reports/refresh-YYYY-MM-DD.md. A human reviews it, edits data/manual_courses.yaml,
    runs scripts/extract.py, the tests, and commits. Nothing is published automatically.
"""
import datetime, difflib, hashlib, json, os, subprocess, sys
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch import fetch, to_text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "data", "source_state.json")
SNAP = os.path.join(ROOT, "raw", "snapshots")

def urls():
    out = []
    from sources import enabled
    for sport in enabled().values():  # disabled sources (enabled: false) are not fetched
        out += [s["url"] for s in sport]
    for c in json.load(open(os.path.join(ROOT, "data", "courses.json")))["courses"]:
        out.append(c["source_url"]); out += c.get("extra_sources") or []
    seen, uniq = set(), []
    for u in out:
        if u not in seen: seen.add(u); uniq.append(u)
    return uniq

def load_state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {}

def save_state(st):
    tmp = STATE + ".tmp"
    json.dump(st, open(tmp, "w"), indent=1, sort_keys=True); os.replace(tmp, STATE)

def main():
    today = datetime.date.today().isoformat()
    force, report_only = "--force" in sys.argv, "--report" in sys.argv
    st = load_state(); os.makedirs(SNAP, exist_ok=True)
    changed = []
    if not report_only:
        for u in urls():
            prev = st.get(u, {})
            if prev.get("checked") == today and not force:
                continue
            m = fetch(u, refresh=True)
            text = to_text(m) if m.get("body") else ""
            h = hashlib.sha256(text.encode()).hexdigest() if text else None
            key = hashlib.sha256(u.encode()).hexdigest()[:16]
            old_p, new_p = os.path.join(SNAP, key + ".prev.txt"), os.path.join(SNAP, key + ".txt")
            rec = {"checked": today, "status": m.get("status"), "error": m.get("error"), "hash": h,
                   "last_hash": prev.get("hash"), "changed": bool(h and prev.get("hash") and h != prev.get("hash"))}
            if text:
                if os.path.exists(new_p): os.replace(new_p, old_p)
                open(new_p, "w").write(text)
            st[u] = rec; save_state(st)
            print(f"{rec['status']} {'CHANGED' if rec['changed'] else ''} {u[:100]}", flush=True)
    # candidate courses
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "extract.py"), "--out",
                    os.path.join(ROOT, "data", "courses.candidate.json")], check=False)
    cur = {c["id"]: c for c in json.load(open(os.path.join(ROOT, "data", "courses.json")))["courses"]}
    cand_p = os.path.join(ROOT, "data", "courses.candidate.json")
    cand = {c["id"]: c for c in json.load(open(cand_p))["courses"]} if os.path.exists(cand_p) else {}
    added = sorted(set(cand) - set(cur)); removed = sorted(set(cur) - set(cand))
    modified = sorted(i for i in set(cur) & set(cand)
                      if {k: v for k, v in cur[i].items() if k != "fetched_at"} != {k: v for k, v in cand[i].items() if k != "fetched_at"})
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    rp = os.path.join(ROOT, "reports", f"refresh-{today}.md")
    with open(rp, "w") as f:
        f.write(f"# Refresh review {today}\n\nNothing below is published until a person reviews it.\n\n")
        f.write("## Pages that changed\n\n")
        for u, r in st.items():
            if r.get("checked") == today and r.get("changed"):
                key = hashlib.sha256(u.encode()).hexdigest()[:16]
                a = open(os.path.join(SNAP, key + ".prev.txt")).read().splitlines() if os.path.exists(os.path.join(SNAP, key + ".prev.txt")) else []
                b = open(os.path.join(SNAP, key + ".txt")).read().splitlines()
                d = list(difflib.unified_diff(a, b, lineterm="", n=1))[:120]
                f.write(f"### {u}\n\n```diff\n" + "\n".join(d) + "\n```\n\n")
        f.write("## Fetch problems\n\n")
        for u, r in st.items():
            if r.get("error"): f.write(f"- {u}: {r['error']}\n")
        f.write(f"\n## Course candidates\n\n- added: {added}\n- removed: {removed}\n- modified: {modified}\n")
    print("report:", rp)

if __name__ == "__main__":
    main()
