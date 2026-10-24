"""One-off: make the PNG brand images from the coach-shield mockup Gus picked (assets/coachbadge-mockup.jpg, cut out by
scripts/emblem.py, never redrawn or recoloured): site/logo.png (256, header icon shown at 40px, logo on the LEFT),
site/og.png (1200x630 share card, emblem on the LEFT), site/logo-512.png (structured-data logo), site/apple-touch-icon.png (180),
site/favicon.png (32), site/favicon.ico (16/32/48) and site/email-logo.png (96, shown at 28px in emails).
Run by hand when the brand changes: python3 scripts/make_images.py  (needs Pillow and numpy; the build only copies the files)."""
import json, os
from PIL import Image, ImageDraw, ImageFont
from emblem import emblem
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
CFG = json.load(open(os.path.join(ROOT, "config", "site.json")))
INK, LIME, WHITE = (11, 31, 51), (198, 244, 50), (255, 255, 255)
FONT = "/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf"
WORD = "/usr/share/fonts/truetype/sand-box/google/Outfit/Outfit-VariableFont_wght.ttf"
E = emblem()

def font(path, size, axes):
    f = ImageFont.truetype(path, size)
    try: f.set_variation_by_axes(axes)
    except Exception: pass
    return f

def icon(size, bg=None, pad=0):
    im = Image.new("RGBA", (size, size), (bg + (255,)) if bg else (0, 0, 0, 0)); s = size - 2 * pad
    im.alpha_composite(E.resize((s, s), Image.LANCZOS), (pad, pad)); return im

def og():
    W, H = 1200, 630
    im = Image.new("RGBA", (W, H), INK + (255,)); d = ImageDraw.Draw(im)
    d.rectangle((0, H - 14, W, H), fill=LIME)
    es = 230; im.alpha_composite(E.resize((es, es), Image.LANCZOS), (70, 130))  # emblem on the LEFT
    x = 70 + es + 30; wf = font(WORD, 112, [800]); wm = CFG["wordmark"]
    yb = 130 + es // 2 + 45
    d.text((x, yb), wm[:5], font=wf, fill=WHITE, anchor="ls")
    d.text((x + d.textlength(wm[:5], font=wf), yb), wm[5:], font=wf, fill=LIME, anchor="ls")
    words, lines, cur, ft = CFG["tagline"].split(), [], "", font(FONT, 42, [32, 600])
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=ft) > W - x - 90: lines.append(cur); cur = w_
        else: cur = t
    lines.append(cur)
    y0 = 130 + es + 20
    for i, ln in enumerate(lines): d.text((x, y0 + i * 58), ln, font=ft, fill=(223, 232, 238))
    im.convert("RGB").save(os.path.join(SITE, "og.png"), optimize=True)

def main():
    og()
    icon(256).save(os.path.join(SITE, "logo.png"), optimize=True)
    icon(512, INK, 40).convert("RGB").save(os.path.join(SITE, "logo-512.png"), optimize=True)
    icon(180, INK, 12).convert("RGB").save(os.path.join(SITE, "apple-touch-icon.png"), optimize=True)
    icon(96).save(os.path.join(SITE, "email-logo.png"), optimize=True)
    icon(32).save(os.path.join(SITE, "favicon.png"), optimize=True)
    ico = {s: icon(s) for s in (16, 32, 48)}
    ico[48].save(os.path.join(SITE, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)], append_images=[ico[16], ico[32]])
    print("wrote site/logo.png, og.png, logo-512.png, apple-touch-icon.png, email-logo.png, favicon.png, favicon.ico")

if __name__ == "__main__":
    main()
