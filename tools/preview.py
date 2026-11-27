"""Fast design preview straight from src/thaana.py (no font build).
Reference glyph in light grey, candidate in translucent blue, 100-unit grid.
usage: preview.py out.png name1,name2,... [--scale 0.25] [--noref] [--cols 4]"""
import sys, os, argparse, importlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); sys.path.insert(0, os.path.join(ROOT, 'src'))
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont, ImageChops
from raster import contours as ref_contours
import stroke, thaana

ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('names')
ap.add_argument('--scale', type=float, default=0.25); ap.add_argument('--noref', action='store_true')
ap.add_argument('--cols', type=int, default=4); ap.add_argument('--x0', type=int, default=-400); ap.add_argument('--x1', type=int, default=2000)
ap.add_argument('--y0', type=int, default=-1000); ap.add_argument('--y1', type=int, default=1900)
a = ap.parse_args()
ref = TTFont(os.path.join(ROOT, 'reference', 'Faruma.ttf'))
names = a.names.split(',')
s = a.scale; cw = int((a.x1 - a.x0) * s); ch = int((a.y1 - a.y0) * s)
cols = min(a.cols, len(names)); rows = (len(names) + cols - 1) // cols
img = Image.new('RGBA', (cols * cw, rows * ch), (255, 255, 255, 255)); d = ImageDraw.Draw(img)
try: fnt = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 13)
except Exception: fnt = None

def fill(conts, ox, oy, col):
    layer = Image.new('1', img.size, 0)
    for c in conts:
        if len(c) < 3: continue
        m = Image.new('1', img.size, 0)
        ImageDraw.Draw(m).polygon([(ox + (x - a.x0) * s, oy + (a.y1 - y) * s) for x, y in c], fill=1)
        layer = ImageChops.logical_xor(layer, m)
    img.alpha_composite(Image.composite(Image.new('RGBA', img.size, col), Image.new('RGBA', img.size, (0, 0, 0, 0)), layer.convert('L')))

for i, n in enumerate(names):
    ox = (i % cols) * cw; oy = (i // cols) * ch
    X = lambda x: ox + (x - a.x0) * s; Y = lambda y: oy + (a.y1 - y) * s
    for gx in range((a.x0 // 100) * 100, a.x1 + 1, 100):
        d.line([(X(gx), oy), (X(gx), oy + ch)], fill=(225, 225, 225) if gx % 500 else (190, 190, 190))
    for gy in range((a.y0 // 100) * 100, a.y1 + 1, 100):
        d.line([(ox, Y(gy)), (ox + cw, Y(gy))], fill=(225, 225, 225) if gy % 500 else (190, 190, 190))
    d.line([(ox, Y(0)), (ox + cw, Y(0))], fill=(255, 80, 80))
    if s >= 0.28:
        for gx in range((a.x0 // 200) * 200, a.x1 + 1, 200): d.text((X(gx) + 2, oy + ch - 14), str(gx), fill=(150, 0, 0), font=fnt)
        for gy in range((a.y0 // 200) * 200, a.y1 + 1, 200): d.text((ox + 2, Y(gy) - 13), str(gy), fill=(150, 0, 0), font=fnt)
    if n in ref['hmtx'].metrics:
        adv = ref['hmtx'][n][0]
        d.line([(X(0), oy), (X(0), oy + ch)], fill=(255, 80, 80)); d.line([(X(adv), oy), (X(adv), oy + ch)], fill=(255, 80, 80))
        if not a.noref:
            fill(ref_contours(ref, n), ox, oy, (0, 0, 0, 60))
    if n in thaana.GLYPHS:
        g = thaana.GLYPHS[n]; g = g() if callable(g) else g
        fill(stroke.finalize(g), ox, oy, (0, 70, 220, 150))
    d.text((ox + 4, oy + 4), n, fill=(0, 0, 0), font=fnt)
    d.rectangle([ox, oy, ox + cw - 1, oy + ch - 1], outline=(120, 120, 120))
img.convert('RGB').save(a.out); print(a.out, img.size)
