import sys, re, urllib.parse
from bs4 import BeautifulSoup
sys.path.insert(0, "scripts"); from fetch import fetch
m = fetch(sys.argv[1]); pat = re.compile(sys.argv[2] if len(sys.argv) > 2 else ".", re.I)
s = BeautifulSoup(m["body"], "html.parser"); seen = set()
for a in s.find_all("a", href=True):
    u = urllib.parse.urljoin(m.get("final_url") or m["url"], a["href"]); t = " ".join(a.get_text().split())[:80]
    if (pat.search(u) or pat.search(t)) and u not in seen:
        seen.add(u); print(t, "|", u)
