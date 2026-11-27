"""Objective comparison of candidate glyphs (from src or a built TTF) vs the reference metrics.
Reports per glyph: bbox deltas, ink-area ratio (weight/colour), blurred-raster similarity (proportion,
not contour identity), advance match.  usage: compare.py [names|all] [--ttf built.ttf] [--json out.json]"""
import sys, os, json, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); sys.path.insert(0, os.path.join(ROOT, 'src'))
import numpy as np
from fontTools.ttLib import TTFont
from shapely.geometry import Polygon
from PIL import Image, ImageDraw, ImageChops, ImageFilter
from raster import contours as font_contours
import stroke, thaana

ap = argparse.ArgumentParser(); ap.add_argument('names', nargs='?', default='all')
ap.add_argument('--ttf'); ap.add_argument('--json')
a = ap.parse_args()
ref = TTFont(os.path.join(ROOT, 'reference', 'Faruma.ttf'))
cand = TTFont(a.ttf) if a.ttf else None
names = list(thaana.GLYPHS) if a.names == 'all' else a.names.split(',')

def area_bbox(conts):
    tot = 0; xs = []; ys = []
    for c in conts:
        if len(c) < 3: continue
        p = Polygon(c); tot += -p.exterior.is_ccw and p.area or 0
        xs += [x for x, y in c]; ys += [y for x, y in c]
    # even-odd area
    img = raster(conts, 0.1)
    return float(np.asarray(img).sum() / 255 / 0.01), (min(xs), min(ys), max(xs), max(ys)) if xs else None

def raster(conts, s, box=(-600, -1100, 2600, 2000)):
    W = int((box[2] - box[0]) * s); H = int((box[3] - box[1]) * s)
    layer = Image.new('1', (W, H), 0)
    for c in conts:
        if len(c) < 3: continue
        m = Image.new('1', (W, H), 0)
        ImageDraw.Draw(m).polygon([((x - box[0]) * s, (box[3] - y) * s) for x, y in c], fill=1)
        layer = ImageChops.logical_xor(layer, m)
    return layer.convert('L')

rows = {}
for n in names:
    rc = font_contours(ref, n)
    if cand: cc = font_contours(cand, n)
    else:
        g = thaana.GLYPHS[n]; g = g() if callable(g) else g; cc = stroke.finalize(g)
    if not rc or not cc: continue
    ra, rb = area_bbox(rc); ca, cb = area_bbox(cc)
    # proportion similarity: heavy blur (~60u) so it measures massing, not contour detail
    R = np.asarray(raster(rc, 0.05).filter(ImageFilter.GaussianBlur(3)), float)
    C = np.asarray(raster(cc, 0.05).filter(ImageFilter.GaussianBlur(3)), float)
    sim = float((R * C).sum() / np.sqrt((R * R).sum() * (C * C).sum()))
    d = [round(cb[i] - rb[i]) for i in range(4)]
    rows[n] = dict(weight=round(ca / ra, 3), bbox_delta=d, sim=round(sim, 4))
    print(f'{n:12s} weight {ca/ra:5.2f}  bboxΔ {d}  massing-sim {sim:.3f}')
if a.json: json.dump(rows, open(a.json, 'w'), indent=1)
