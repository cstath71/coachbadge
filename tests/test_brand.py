"""Brand assets: the coach-shield emblem is the mockup Gus picked (assets/coachbadge-mockup.jpg), cut out, not redrawn.
No vector redraw anywhere; favicons and PNGs ship at the right sizes; header logo on the LEFT."""
import os, struct, sys, unittest
from bs4 import BeautifulSoup
try:
    import numpy, PIL  # only needed to re-cut the emblem; CI builds without them
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST, SITE = os.path.join(ROOT, "dist"), os.path.join(ROOT, "site")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

def png_size(p):
    b = open(p, "rb").read(24); assert b[:8] == b"\x89PNG\r\n\x1a\n", p
    return struct.unpack(">II", b[16:24])

class Brand(unittest.TestCase):
    def test_no_vector_redraw(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "scripts", "brand.py")))
        self.assertFalse(os.path.exists(os.path.join(SITE, "brand")))
        self.assertFalse(os.path.exists(os.path.join(DIST, "brand")))
        self.assertFalse(os.path.exists(os.path.join(DIST, "favicon.svg")))
        self.assertNotIn("<svg", open(os.path.join(DIST, "index.html")).read().split("</header>")[0])

    @unittest.skipUnless(HAVE_PIL, "needs Pillow + numpy")
    def test_emblem_is_the_mockup_pixels(self):
        from PIL import Image
        from emblem import emblem, SRC, BOX
        self.assertTrue(os.path.exists(SRC))
        e = emblem()
        self.assertEqual(e.width, e.height)
        cut = Image.open(SRC).convert("RGB").crop(BOX)
        # emblem pixels inside the shield are byte-identical to the crop at the same offset
        found = 0
        for (x, y) in ((169, 230), (69, 130), (120, 300)):  # crop coords well inside the shield
            want = cut.getpixel((x, y))
            got = [e.getpixel((x + dx, y + dy))[:3] for dx in range(-30, 40) for dy in range(-30, 40)
                   if 0 <= x + dx < e.width and 0 <= y + dy < e.height and e.getpixel((x + dx, y + dy))[3] == 255]
            found += want in got
        self.assertEqual(found, 3)
        self.assertEqual(e.getpixel((0, 0))[3], 0)  # white sheet removed

    def test_favicons_and_pngs(self):
        ico = open(os.path.join(DIST, "favicon.ico"), "rb").read()
        self.assertEqual(ico[:4], b"\x00\x00\x01\x00")
        n = struct.unpack("<H", ico[4:6])[0]
        self.assertEqual(sorted((ico[6 + 16*i] or 256) for i in range(n)), [16, 32, 48])
        for f, s in (("favicon.png", 32), ("apple-touch-icon.png", 180), ("logo-512.png", 512), ("email-logo.png", 96), ("logo.png", 256)):
            with self.subTest(f): self.assertEqual(png_size(os.path.join(DIST, f)), (s, s))
            self.assertEqual(open(os.path.join(DIST, f), "rb").read(), open(os.path.join(SITE, f), "rb").read())
        self.assertEqual(png_size(os.path.join(DIST, "og.png")), (1200, 630))

    def test_head_links_and_header_logo(self):
        s = BeautifulSoup(open(os.path.join(DIST, "index.html")).read(), "html.parser")
        hrefs = {l["href"] for l in s.find_all("link", rel=lambda r: r and ("icon" in r or "apple-touch-icon" in r))}
        self.assertEqual(hrefs, {"favicon.ico", "favicon.png", "apple-touch-icon.png"})
        wm = s.select_one("header.top #wordmark")
        first = wm.find_all(recursive=False)[0]
        self.assertEqual(first.name, "img")  # logo LEFT of the wordmark
        self.assertEqual(first["src"], "logo.png"); self.assertEqual(first.get("alt"), "CoachBadge logo")

if __name__ == "__main__":
    unittest.main()
