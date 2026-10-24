"""Brand assets for CoachBadge, hand-written SVG (coach shield). Writes site/brand/*.svg.
Run by hand when the brand changes: python3 scripts/brand.py  (then scripts/make_images.py for the PNGs)."""
import math, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INK, PITCH, LIME, WHITE = "#0b1f33", "#0f8a46", "#c6f432", "#fff"

SHIELD = "M32 2.5 56.5 9.5V29c0 15.5-9.8 26-24.5 32.5C17.3 55 7.5 44.5 7.5 29V9.5z"

def pent(cx, cy, r, rot=0):
    pts = [(cx + r*math.sin(math.radians(rot + 72*i)), cy - r*math.cos(math.radians(rot + 72*i))) for i in range(5)]
    return "M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + "z"

def ball(cx, cy, r):
    """Lime football: navy centre pentagon, five clipped edge patches."""
    edge = "".join(pent(cx + r*1.02*math.sin(math.radians(72*i)), cy - r*1.02*math.cos(math.radians(72*i)), r*.34, 72*i + 180) for i in range(5))
    seams = "".join(f"M{cx + r*.32*math.sin(math.radians(72*i)):.2f} {cy - r*.32*math.cos(math.radians(72*i)):.2f}L{cx + r*.72*math.sin(math.radians(72*i)):.2f} {cy - r*.72*math.cos(math.radians(72*i)):.2f}" for i in range(5))
    return (f'<clipPath id="cb-ball"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath><circle cx="{cx}" cy="{cy}" r="{r}" fill="{LIME}"/>'
            f'<g clip-path="url(#cb-ball)" fill="{INK}"><path d="{pent(cx, cy, r*.32)}{edge}"/>'
            f'<path d="{seams}" stroke="{INK}" stroke-width="{r*.08:.2f}" stroke-linecap="round"/></g>')

def coach(full=True):
    """White football coach in a tracksuit (bare head), pointing forward, clipboard in the other hand; lime football at the feet."""
    w, p = WHITE, PITCH
    g = [
        f'<circle cx="28.3" cy="13.8" r="4.3" fill="{w}"/>',                                   # head
        f'<path d="M21.2 23c0-2.4 2-3.6 4.8-3.7h4.6c2.6.1 4.4 1.5 4.4 3.9L33.6 38H23z" fill="{w}"/>',  # tracksuit top
        f'<path d="M33.4 22.6 45.4 16.9" stroke="{w}" stroke-width="4.6" stroke-linecap="round"/>',    # pointing arm
        f'<path d="M45.4 16.9 49.6 15.5" stroke="{w}" stroke-width="2.2" stroke-linecap="round"/>',    # index finger
        f'<path d="M23 37.4h5.4l-4.2 14h-4z" fill="{w}"/>',                                      # back leg
        f'<path d="M28.6 37.4h5.2l2.6 13.4h-4z" fill="{w}"/>',                                   # front leg
        f'<path d="M19.6 50.6h5c1.6 0 2.6 1.1 2.6 2.6h-7.6z" fill="{w}"/>',                      # back boot
        f'<path d="M32.2 50.2h5c1.7 0 2.7 1.1 2.7 2.6h-7.7z" fill="{w}"/>',                      # front boot
    ]
    if full:
        g += [
            f'<path d="M26.4 19.4 28.3 22.2 30.2 19.4M28.3 22.2V38" stroke="{p}" stroke-width=".9" fill="none"/>',  # collar + zip
            f'<path d="M24.1 38.8 21.5 50M32.9 38.8 35.1 50" stroke="{p}" stroke-width=".8" stroke-linecap="round"/>',  # trouser stripes
            f'<path d="M22.4 22.8 18.4 29.6" stroke="{w}" stroke-width="3.8" stroke-linecap="round"/>',  # far arm
            f'<g transform="rotate(-12 16.4 31.6)"><rect x="11.8" y="26" width="9.2" height="11.6" rx="1.3" fill="{w}" stroke="{p}" stroke-width="1.2"/>'
            f'<rect x="14.2" y="24.9" width="4.4" height="2.4" rx=".8" fill="{p}"/>'
            f'<path d="M14 30.2h4.8M14 32.6h4.8M14 35h3" stroke="{p}" stroke-width=".9" stroke-linecap="round"/></g>',
            ball(43.4, 47.6, 5.3),
        ]
    else:
        g += [f'<path d="M22.4 22.8 19.4 32" stroke="{w}" stroke-width="3.8" stroke-linecap="round"/>',
              f'<circle cx="44.6" cy="48" r="6" fill="{LIME}"/>']
    return "".join(g)

def icon(full=True, size=None):
    wh = f' width="{size}" height="{size}"' if size else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"{wh}>'
            f'<path d="{SHIELD}" fill="{PITCH}"/>{coach(full)}</svg>')

FONT = "/usr/share/fonts/truetype/sand-box/google/Outfit/Outfit-VariableFont_wght.ttf"

def wordmark_paths(text="CoachBadge", split=5, colors=(INK, PITCH), wght=750, size=40, x0=0.0, baseline=0.0):
    """Wordmark as SVG paths (no font needed at render time). Returns (svg fragment, advance width)."""
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    f = instantiateVariableFont(TTFont(FONT), {"wght": wght}); gs = f.getGlyphSet(); cmap = f.getBestCmap()
    upm = f["head"].unitsPerEm; k = size / upm; x = x0; parts = ["", ""]
    for i, ch in enumerate(text):
        g = cmap[ord(ch)]; pen = SVGPathPen(gs)
        gs[g].draw(TransformPen(pen, (k, 0, 0, -k, x, baseline)))
        parts[0 if i < split else 1] += pen.getCommands(); x += gs[g].width * k - size * .01
    frag = "".join(f'<path fill="{c}" d="{d}"/>' for c, d in zip(colors, parts))
    return frag, x - x0

def lockup(colors=(INK, PITCH)):
    inner = icon(True)[icon(True).index(">") + 1:-6]
    wm, w = wordmark_paths(colors=colors, size=36, x0=73, baseline=44.5)
    W = 73 + w + 3
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.1f} 64">{inner}{wm}</svg>')

if __name__ == "__main__":
    out = os.path.join(ROOT, "site", "brand"); os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "coachbadge-icon.svg"), "w").write(icon(True))
    open(os.path.join(out, "coachbadge-icon-small.svg"), "w").write(icon(False))
    open(os.path.join(out, "coachbadge-lockup.svg"), "w").write(lockup())
    open(os.path.join(out, "coachbadge-lockup-dark.svg"), "w").write(lockup((WHITE, LIME)))  # for navy backgrounds
    print("ok")
