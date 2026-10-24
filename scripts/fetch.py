"""Polite fetcher: robots.txt check, descriptive User-Agent, 1 request per host per 3 s, on-disk cache.
Usage: python3 scripts/fetch.py URL [--text] [--refresh]"""
import hashlib, os, sys, time, urllib.parse, urllib.robotparser, urllib.request, json, re, subprocess
UA = "CoachBadgeBot/1.0 (+https://coachbadge.com/methodology.html; weekly check of public course pages)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "raw", "cache")
_last = {}
_robots = {}

def iri(url):
    """Percent-encode non-ASCII characters in a URL (e.g. 'OÖFV-...pdf') so urllib can request it."""
    return urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")

def robots_ok(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                rp.disallow_all = True
            else:
                rp.allow_all = True
        except Exception:
            rp.allow_all = True
        _robots[base] = rp
    return _robots[base].can_fetch(UA, url)

def fetch(url, refresh=False):
    """Returns dict(url, status, body bytes, ctype, fetched_at, error)."""
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()[:24]
    meta_p = os.path.join(CACHE, key + ".json"); body_p = os.path.join(CACHE, key + ".body")
    if not refresh and os.path.exists(meta_p):
        meta = json.load(open(meta_p)); meta["body"] = open(body_p, "rb").read() if os.path.exists(body_p) else b""
        return meta
    meta = {"url": url, "fetched_at": time.strftime("%Y-%m-%d"), "status": None, "ctype": "", "error": None}
    body = b""
    if not robots_ok(url):
        meta["error"] = "disallowed by robots.txt"
    else:
        host = urllib.parse.urlsplit(url).netloc
        wait = 3 - (time.time() - _last.get(host, 0))
        if wait > 0: time.sleep(wait)
        _last[host] = time.time()
        try:
            req = urllib.request.Request(iri(url), headers={"User-Agent": UA, "Accept-Language": "en,de;q=0.8,*;q=0.5"})
            with urllib.request.urlopen(req, timeout=40) as r:
                body = r.read(); meta["status"] = r.status; meta["ctype"] = r.headers.get("Content-Type", "")
                meta["final_url"] = r.geturl()
        except urllib.error.HTTPError as e:
            meta["status"] = e.code; meta["error"] = f"HTTP {e.code}"
        except Exception as e:
            meta["error"] = type(e).__name__ + ": " + str(e)[:150]
    json.dump(meta, open(meta_p, "w"), indent=1)
    open(body_p, "wb").write(body)
    meta["body"] = body
    return meta

def to_text(meta):
    b = meta.get("body") or b""
    if b[:4] == b"%PDF" or "pdf" in meta.get("ctype", ""):
        p = subprocess.run(["pdftotext", "-layout", "-", "-"], input=b, capture_output=True)
        return p.stdout.decode("utf-8", "replace")
    try:
        from bs4 import BeautifulSoup
        s = BeautifulSoup(b, "html.parser")
        for t in s(["script", "style", "noscript", "svg"]): t.decompose()
        txt = s.get_text("\n")
    except Exception:
        txt = re.sub(r"<[^>]+>", " ", b.decode("utf-8", "replace"))
    return re.sub(r"\n\s*\n+", "\n", txt)

if __name__ == "__main__":
    m = fetch(sys.argv[1], refresh="--refresh" in sys.argv)
    print({k: v for k, v in m.items() if k != "body"}, len(m.get("body") or b""))
    if "--text" in sys.argv:
        print(to_text(m))
