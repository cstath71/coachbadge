"""One-off: draw the PNG brand images from the hand-written SVGs in site/brand/ (made by scripts/brand.py):
site/og.png (1200x630 share card, logo on the LEFT), site/logo-512.png (structured-data logo), site/apple-touch-icon.png (180),
site/favicon.ico (16/32/48) and site/email-logo.png (96, shown at 28px in emails; Gmail does not show SVG).
Run by hand when the brand changes: python3 scripts/brand.py && python3 scripts/make_images.py
Needs Pillow and cairosvg (not needed by the build, which only copies the files)."""
import io, json, os
import cairosvg
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE, BRAND = os.path.join(ROOT, "site"), os.path.join(ROOT, "site", "brand")
CFG = json.load(open(os.path.join(ROOT, "config", "site.json")))
INK, LIME = (11, 31, 51), (198, 244, 50)
FONT = "/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf"

def svg(name, w, h=None):
    png = cairosvg.svg2png(url=os.path.join(BRAND, name), output_width=w, output_height=h)
    return Image.open(io.BytesIO(png)).convert("RGBA")

def font(size, wght):
    f = ImageFont.truetype(FONT, size)
    try: f.set_variation_by_axes([size if size < 32 else 32, wght])
    except Exception: pass
    return f

def og():
    W, H = 1200, 630
    im = Image.new("RGBA", (W, H), INK + (255,)); d = ImageDraw.Draw(im)
    d.rectangle((0, H - 14, W, H), fill=LIME)
    lk = svg("coachbadge-lockup-dark.svg", 860)  # icon left, wordmark right
    im.alpha_composite(lk, (80, 150))
    x = 80 + int(860 * 73 / float(open(os.path.join(BRAND, "coachbadge-lockup-dark.svg")).read().split('viewBox="0 0 ')[1].split()[0]))
    words, lines, cur, ft = CFG["tagline"].split(), [], "", font(42, 600)
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=ft) > W - x - 90: lines.append(cur); cur = w_
        else: cur = t
    lines.append(cur)
    y0 = 150 + lk.height + 34
    for i, ln in enumerate(lines): d.text((x, y0 + i * 58), ln, font=ft, fill=(223, 232, 238))
    im.convert("RGB").save(os.path.join(SITE, "og.png"), optimize=True)

def square(size, pad, variant="coachbadge-icon.svg"):
    im = Image.new("RGBA", (size, size), INK + (255,)); s = size - 2 * pad
    im.alpha_composite(svg(variant, s, s), (pad, pad)); return im.convert("RGB")

def main():
    og()
    square(512, 40).save(os.path.join(SITE, "logo-512.png"), optimize=True)
    square(180, 16).save(os.path.join(SITE, "apple-touch-icon.png"), optimize=True)
    svg("coachbadge-icon-small.svg", 96, 96).save(os.path.join(SITE, "email-logo.png"), optimize=True)
    ico = {16: svg("coachbadge-icon-small.svg", 16, 16), 32: svg("coachbadge-icon-small.svg", 32, 32), 48: svg("coachbadge-icon.svg", 48, 48)}
    ico[48].save(os.path.join(SITE, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)], append_images=[ico[16], ico[32]])
    print("wrote site/og.png, logo-512.png, apple-touch-icon.png, email-logo.png, favicon.ico")

if __name__ == "__main__":
    main()
