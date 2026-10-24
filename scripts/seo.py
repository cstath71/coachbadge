"""SEO + answer-engine helpers for scripts/build.py (same pattern as the other sites): robots.txt with explicit AI-crawler
groups, JSON-LD (WebSite, Organization, BreadcrumbList, FAQPage), visible breadcrumbs and FAQ blocks, sitemap.xml and the
IndexNow key file. Nothing here holds a number: every count is passed in by build.py, computed from data/courses.json."""
import html, json, re

INDEXNOW_KEY = "9e2709cff373eaba8f7873ee6317a443"  # public by design: served at /<key>.txt; scripts/indexnow.py pings with it
# Search engines and AI assistants are welcome to crawl and cite the site.
AI_BOTS = ("Googlebot", "Bingbot", "DuckDuckBot", "Applebot", "Applebot-Extended", "Google-Extended",
           "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User",
           "PerplexityBot", "Perplexity-User", "CCBot", "Amazonbot", "meta-externalagent", "MistralAI-User", "YandexBot")

def text(h):
    """Visible text of an HTML fragment (used so FAQ JSON-LD repeats exactly what the page shows)."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h))).strip()

def ld_script(o):
    return '<script type="application/ld+json">' + json.dumps(o, ensure_ascii=False).replace("</", "<\\/") + "</script>"

def org(base, brand):
    return {"@type": "Organization", "@id": base + "#org", "name": brand, "url": base, "logo": base + "logo-512.png"}

def website(base, brand, desc):
    return {"@type": "WebSite", "@id": base + "#website", "name": brand, "url": base, "description": desc,
            "inLanguage": "en", "publisher": {"@id": base + "#org"}}

def breadcrumb_ld(base, crumbs):
    """crumbs: [(name, root-relative path)]; '' is the home page."""
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": base + p} for i, (n, p) in enumerate(crumbs)]}

def breadcrumb_html(crumbs, r):
    li = []
    for i, (n, p) in enumerate(crumbs):
        if i == len(crumbs) - 1: li.append(f'<li aria-current="page">{html.escape(n)}</li>')
        else: li.append(f'<li><a href="{(r + p) or "./"}">{html.escape(n)}</a></li>')
    return f'<nav class="crumbs" aria-label="Breadcrumb"><div class="wrap"><ol>{"".join(li)}</ol></div></nav>'

def faq_html(faq, h="Frequently asked questions"):
    """faq: [(question, answer HTML)]. Visible block; faq_ld() repeats the same text."""
    return (f'<section class="faq" id="faq" aria-labelledby="faq-h"><h2 id="faq-h"><span class="bar"></span>{html.escape(h)}</h2>'
            + "".join(f'<h3>{html.escape(q)}</h3><p>{a}</p>' for q, a in faq) + "</section>")

def faq_ld(faq):
    return {"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": text(a)}} for q, a in faq]}

def robots_txt(base):
    return ("User-agent: *\nAllow: /\n\n# Search engines and AI assistants are welcome to crawl and cite this site.\n"
            + "".join(f"User-agent: {b}\n" for b in AI_BOTS) + "Allow: /\n\n" + f"Sitemap: {base}sitemap.xml\n")

def sitemap_xml(entries):
    """entries: [(absolute url, lastmod YYYY-MM-DD)]."""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"<url><loc>{html.escape(u)}</loc><lastmod>{d}</lastmod></url>\n" for u, d in entries) + "</urlset>\n")

def and_list(xs):
    xs = list(xs)
    if not xs: return ""
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]
