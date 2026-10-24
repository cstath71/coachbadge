"""Render a JavaScript-only page in headless Chromium, with the same robots.txt check, CoachBadgeBot user agent,
3 s per host pacing and on-disk cache as fetch.py. A JavaScript page is not a block; a 403, a bot challenge or a
login is, and render() gives up on those exactly like fetch() (it never clicks through or retries around them).
Usage: python3 scripts/render.py URL [--text] [--refresh]"""
import hashlib, json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch import UA, CACHE, robots_ok, to_text, _last

CHALLENGE = ("cf-challenge", "challenge-platform", "Just a moment...", "Attention Required!", "captcha")

def render(url, refresh=False, wait_ms=2500):
    os.makedirs(CACHE, exist_ok=True)
    key = "r-" + hashlib.sha256(url.encode()).hexdigest()[:24]
    meta_p = os.path.join(CACHE, key + ".json"); body_p = os.path.join(CACHE, key + ".body")
    if not refresh and os.path.exists(meta_p):
        meta = json.load(open(meta_p)); meta["body"] = open(body_p, "rb").read() if os.path.exists(body_p) else b""
        return meta
    meta = {"url": url, "fetched_at": time.strftime("%Y-%m-%d"), "status": None, "ctype": "text/html", "error": None, "rendered": True}
    body = b""
    if not robots_ok(url):
        meta["error"] = "disallowed by robots.txt"
    else:
        host = urllib.parse.urlsplit(url).netloc
        wait = 3 - (time.time() - _last.get(host, 0))
        if wait > 0: time.sleep(wait)
        _last[host] = time.time()
        from playwright.sync_api import sync_playwright
        try:
            with sync_playwright() as p:
                try:
                    b = p.chromium.launch(headless=True)
                except Exception:  # no bundled browser: use the installed Chrome
                    b = p.chromium.launch(headless=True, channel="chrome")
                pg = b.new_page(user_agent=UA, locale="de-AT")
                r = pg.goto(url, wait_until="networkidle", timeout=60000)
                pg.wait_for_timeout(wait_ms)
                meta["status"] = r.status if r else None
                meta["final_url"] = pg.url
                html = pg.content()
                b.close()
            if meta["status"] and meta["status"] >= 400:
                meta["error"] = f"HTTP {meta['status']}"
            elif any(c in html for c in CHALLENGE):
                meta["error"] = "bot challenge page; not bypassed"
            else:
                body = html.encode("utf-8")
        except Exception as ex:
            meta["error"] = type(ex).__name__ + ": " + str(ex)[:150]
    json.dump(meta, open(meta_p, "w"), indent=1)
    open(body_p, "wb").write(body)
    meta["body"] = body
    return meta

def get(url, rendered=False, refresh=False):
    """fetch() or render(), chosen by a source's/course's `render: true` flag."""
    if rendered: return render(url, refresh=refresh)
    from fetch import fetch
    return fetch(url, refresh=refresh)

if __name__ == "__main__":
    m = render(sys.argv[1], refresh="--refresh" in sys.argv)
    print({k: v for k, v in m.items() if k != "body"}, len(m.get("body") or b""))
    if "--text" in sys.argv: print(to_text(m))
