"""Brand assets: coach-shield icon and lockup are clean SVG (no raster, no fonts), favicons and PNGs ship at the right sizes."""
import os, re, struct, unittest
from bs4 import BeautifulSoup
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST, BRAND = os.path.join(ROOT, "dist"), os.path.join(ROOT, "site", "brand")
SVGS = ("coachbadge-icon.svg", "coachbadge-icon-small.svg", "coachbadge-lockup.svg", "coachbadge-lockup-dark.svg")

def png_size(p):
    b = open(p, "rb").read(24); assert b[:8] == b"\x89PNG\r\n\x1a\n", p
    return struct.unpack(">II", b[16:24])

class Brand(unittest.TestCase):
    def test_svgs_are_clean(self):
        for f in SVGS:
            with self.subTest(f):
                s = open(os.path.join(BRAND, f)).read()
                self.assertTrue(s.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox='))
                self.assertNotRegex(s, r"<image|<text|font-family|@import|href=\"http|data:")
                self.assertIn("#0f8a46", s)  # pitch-green shield
                self.assertTrue(os.path.exists(os.path.join(DIST, "brand", f)))

    def test_lockup_icon_left_of_wordmark(self):
        s = open(os.path.join(BRAND, "coachbadge-lockup.svg")).read()
        self.assertLess(s.index("#0f8a46"), s.index('fill="#0b1f33" d='))  # shield drawn first, wordmark after
        nums = [float(n) for n in re.findall(r"M(-?[\d.]+)", s.split('fill="#0b1f33" d=')[1])[:1]]
        self.assertGreater(nums[0], 64)  # wordmark starts right of the 64-unit icon

    def test_favicons(self):
        self.assertEqual(open(os.path.join(DIST, "favicon.svg")).read(), open(os.path.join(BRAND, "coachbadge-icon-small.svg")).read())
        ico = open(os.path.join(DIST, "favicon.ico"), "rb").read()
        self.assertEqual(ico[:4], b"\x00\x00\x01\x00")
        n = struct.unpack("<H", ico[4:6])[0]
        sizes = sorted((ico[6 + 16*i] or 256) for i in range(n))
        self.assertEqual(sizes, [16, 32, 48])
        self.assertEqual(png_size(os.path.join(DIST, "apple-touch-icon.png")), (180, 180))
        self.assertEqual(png_size(os.path.join(DIST, "logo-512.png")), (512, 512))
        self.assertEqual(png_size(os.path.join(DIST, "email-logo.png")), (96, 96))

    def test_head_links_and_header_icon(self):
        s = BeautifulSoup(open(os.path.join(DIST, "index.html")).read(), "html.parser")
        hrefs = {l["href"] for l in s.find_all("link", rel=lambda r: r and ("icon" in r or "apple-touch-icon" in r))}
        self.assertEqual(hrefs, {"favicon.ico", "favicon.svg", "apple-touch-icon.png"})
        svg = s.select_one("header.top #wordmark > svg")
        self.assertIsNotNone(svg); self.assertEqual(svg.get("aria-hidden"), "true")
        self.assertEqual(s.select_one("header.top #wordmark").find_all(recursive=False)[0].name, "svg")  # icon LEFT of the wordmark

if __name__ == "__main__":
    unittest.main()
