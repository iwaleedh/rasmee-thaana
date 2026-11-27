"""Tune a few skeleton turning points of one glyph to maximise blurred massing similarity with the
reference (proportion/placement at ~60u blur, never contour detail). Prints the best path.
usage: massing_opt.py NAME 'template with {0}..{n}' x0,y0,x1,y1,... [iters] [step]"""
import sys, os, random
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools')); sys.path.insert(0, os.path.join(ROOT, 'src'))
import numpy as np
from PIL import Image, ImageDraw, ImageChops, ImageFilter
from fontTools.ttLib import TTFont
from raster import contours
import stroke, thaana
name, tmpl, init = sys.argv[1], sys.argv[2], [float(v) for v in sys.argv[3].split(',')]
iters = int(sys.argv[4]) if len(sys.argv) > 4 else 120; step = float(sys.argv[5]) if len(sys.argv) > 5 else 40
kw = eval(sys.argv[6]) if len(sys.argv) > 6 else {}
WIN = [float(v) for v in sys.argv[7].split(',')] if len(sys.argv) > 7 else None
RES = float(sys.argv[8]) if len(sys.argv) > 8 else 0.05
FIXED = kw.pop('fixed', []) if isinstance(kw, dict) else []
ref = TTFont(os.path.join(ROOT, 'reference', 'Faruma.ttf'))
def ras(conts, s=None, box=(-600, -1100, 2600, 2000)):
    s = s or RES
    if WIN: box = (WIN[0] - 150, WIN[1] - 150, WIN[2] + 150, WIN[3] + 150)
    W = int((box[2] - box[0]) * s); H = int((box[3] - box[1]) * s); L = Image.new('1', (W, H), 0)
    for c in conts:
        if len(c) < 3: continue
        m = Image.new('1', (W, H), 0); ImageDraw.Draw(m).polygon([((x - box[0]) * s, (box[3] - y) * s) for x, y in c], fill=1)
        L = ImageChops.logical_xor(L, m)
    A = np.asarray(L.convert('L').filter(ImageFilter.GaussianBlur(3 if RES <= 0.05 else 2)), float)
    return A
Rr = ras(contours(ref, name))
def score(p):
    if tmpl.startswith('CR'):
        pts = [(p[i], p[i + 1]) for i in range(0, len(p), 2)]
        path = thaana._cr(pts, 0.9)
    else:
        path = tmpl.format(*[round(v) for v in p])
    extra = kw.pop('_fixed', None) if isinstance(kw, dict) else None
    fixed = FIXED
    fn = lambda: [stroke.stroke(path, **kw)] + [stroke.stroke(*f[0], **f[1]) for f in fixed]
    C = ras(stroke.finalize(thaana._aligned(name, fn)()))
    return float((Rr * C).sum() / np.sqrt((Rr * Rr).sum() * (C * C).sum())), path
best = np.array(init); bs, bp = score(best); print('start', round(bs, 4))
rng = random.Random(1)
for i in range(iters):
    cand = best + np.array([rng.gauss(0, step) for _ in best])
    sc, p = score(cand)
    if sc > bs: best, bs, bp = cand, sc, p; print(i, round(bs, 4))
print('BEST', round(bs, 4)); print(bp)
