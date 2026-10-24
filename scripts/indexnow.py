#!/usr/bin/env python3
"""Tell IndexNow search engines (Bing, Yandex, Seznam, Naver...) which URLs changed: every <loc> in dist/sitemap.xml.
Free, no account: the key file /<key>.txt (written by scripts/build.py from scripts/seo.py) proves we own the site.
Run after a deploy is live:  python3 scripts/indexnow.py   (--dry prints the payload only, sends nothing)"""
import json, os, re, sys, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo import INDEXNOW_KEY as KEY
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "config", "site.json")))
SITE = CFG["base_url"].rstrip("/"); HOST = SITE.split("://", 1)[1]

def payload():
    urls = re.findall(r"<loc>(.*?)</loc>", open(os.path.join(ROOT, "dist", "sitemap.xml")).read())
    urls = [u for u in urls if u.startswith(SITE + "/")][:10000]
    return urls, {"host": HOST, "key": KEY, "keyLocation": f"{SITE}/{KEY}.txt", "urlList": urls}

if __name__ == "__main__":
    urls, body = payload()
    if "--dry" in sys.argv: print(len(urls), "urls", json.dumps(body)[:400]); sys.exit()
    # refuse to ping unless the live key file answers, or the engines would reject (and remember) a bad key
    try: live = urllib.request.urlopen(f"{SITE}/{KEY}.txt", timeout=30).read().decode().strip()
    except Exception as x: sys.exit(f"key file not reachable yet: {x}")
    if live != KEY: sys.exit("live key file does not match; deploy first")
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        r = urllib.request.urlopen(req, timeout=60); print("IndexNow", r.status, len(urls), "urls")
    except urllib.error.HTTPError as x:
        print("IndexNow HTTP", x.code, x.read()[:300]); sys.exit(1)
