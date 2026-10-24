"""One-off: draw site/og.png (1200x630 share card, badge on the LEFT) and site/logo-512.png (square logo for
structured data) from the same shield as the header SVG. Run by hand when the brand changes: python3 scripts/make_images.py
Needs Pillow (not needed by the build, which only copies the PNGs)."""
import json, os
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "config", "site.json")))
INK, LIME, PITCH = (11, 31, 51), (198, 244, 50), (15, 138, 70)
FONT = "/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf"

def bez(p0, p1, p2, p3, n=40):
    return [tuple((1-t)**3*a + 3*(1-t)**2*t*b + 3*(1-t)*t**2*c + t**3*d for a, b, c, d in zip(p0, p1, p2, p3)) for t in (i/n for i in range(1, n+1))]

def shield(draw, ox, oy, s):
    P = lambda pts: [(ox + x*s, oy + y*s) for x, y in pts]
    outer = [(20, 2), (35, 8), (35, 19)] + bez((35, 19), (35, 28), (28.5, 35), (20, 38)) + bez((20, 38), (11.5, 35), (5, 28), (5, 19)) + [(5, 8)]
    inner = [(20, 6), (31, 10.5), (31, 19)] + bez((31, 19), (31, 26), (26.2, 31.6), (20, 34)) + bez((20, 34), (13.8, 31.6), (9, 26), (9, 19)) + [(9, 10.5)]
    draw.polygon(P(outer), fill=LIME); draw.polygon(P(inner), fill=INK)
    tick = P([(13.5, 20), (18, 24.5), (26.5, 15.5)]); w = int(3.2*s)
    draw.line(tick, fill=LIME, width=w, joint="curve")
    for x, y in (tick[0], tick[-1]): draw.ellipse((x-w/2, y-w/2, x+w/2, y+w/2), fill=LIME)

def font(size, wght):
    f = ImageFont.truetype(FONT, size)
    try: f.set_variation_by_axes([size if size < 32 else 32, wght])
    except Exception: pass
    return f

def og():
    S = 2; W, H = 1200*S, 630*S
    im = Image.new("RGB", (W, H), INK); d = ImageDraw.Draw(im)
    d.rectangle((0, H-14*S, W, H), fill=LIME)
    shield(d, 70*S, 150*S, 7.5*S)  # left
    wm = CFG["wordmark"]; f = font(120*S, 900); x, y = 400*S, 200*S
    d.text((x, y), wm[:5], font=f, fill=(255, 255, 255)); d.text((x + d.textlength(wm[:5], font=f), y), wm[5:], font=f, fill=LIME)
    words, lines, cur, ft = CFG["tagline"].split(), [], "", font(44*S, 600)
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=ft) > 720*S: lines.append(cur); cur = w_
        else: cur = t
    lines.append(cur)
    for i, ln in enumerate(lines): d.text((x, 360*S + i*60*S), ln, font=ft, fill=(223, 232, 238))
    im.resize((1200, 630), Image.LANCZOS).save(os.path.join(ROOT, "site", "og.png"), optimize=True)

def logo():
    S = 4; im = Image.new("RGB", (512*S, 512*S), INK); d = ImageDraw.Draw(im)
    shield(d, 56*S, 56*S, 10*S)
    im.resize((512, 512), Image.LANCZOS).save(os.path.join(ROOT, "site", "logo-512.png"), optimize=True)

if __name__ == "__main__":
    og(); logo(); print("wrote site/og.png, site/logo-512.png")
