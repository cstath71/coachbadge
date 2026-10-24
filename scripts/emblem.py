"""Cut the coach-shield emblem out of the logo mockup Gus picked (assets/coachbadge-mockup.jpg), pixel for pixel.
The drawing is not redrawn or recoloured: the crop keeps the mockup's own pixels, and only the plain white sheet
around the shield is made transparent (edge pixels are un-mixed from white so there is no white halo on the dark header).
Returns an RGBA image, square, emblem centred."""
import os
from collections import deque
import numpy as np
from PIL import Image, ImageFilter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "coachbadge-mockup.jpg")
BOX = (131, 170, 416, 527)  # around the shield only (shield spans x 151-395, y 190-506 in the 1280x720 mockup); wordmark starts right of x 430

def emblem():
    im = Image.open(SRC).convert("RGB").crop(BOX)
    a = np.asarray(im).astype(float); H, W = a.shape[:2]
    white = a.min(2) > 200
    out = np.zeros((H, W), bool); out[0, 0] = True; q = deque([(0, 0)])
    while q:  # sheet = near-white pixels connected to the border (the coach's white body inside the shield is not connected)
        y, x = q.popleft()
        for Y, X in ((y+1, x), (y-1, x), (y, x+1), (y, x-1)):
            if 0 <= Y < H and 0 <= X < W and not out[Y, X] and white[Y, X]:
                out[Y, X] = True; q.append((Y, X))
    band = np.asarray(Image.fromarray((out * 255).astype("uint8")).filter(ImageFilter.MaxFilter(7))) > 0
    green = np.array([74., 161., 64.])  # the mockup's shield green, sampled
    est = np.clip(((255 - a[..., 0]) / (255 - green[0]) + (255 - a[..., 2]) / (255 - green[2])) / 2, 0, 1)
    alpha = np.where(band, est, 1.0); alpha[alpha < 0.06] = 0
    rgb = a.copy(); m = band & (alpha > 0)
    rgb[m] = np.clip((a[m] - (1 - alpha[m, None]) * 255) / alpha[m, None], 0, 255)
    rgba = np.dstack([rgb, alpha * 255]).round().astype("uint8")
    img = Image.fromarray(rgba, "RGBA")
    l, t, r, b = img.getbbox(); img = img.crop((l, t, r, b))
    s = max(img.size) + 4; sq = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sq.alpha_composite(img, ((s - img.width) // 2, (s - img.height) // 2))
    return sq

if __name__ == "__main__":
    print(emblem().size)
