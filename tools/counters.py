"""Counter (hole) areas per glyph: reference vs candidate. usage: counters.py font.ttf"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
from fontTools.ttLib import TTFont
from shapely.geometry import Polygon
from raster import contours
def holes(f, n):
    g = None
    for c in contours(f, n):
        if len(c) < 3: continue
        p = Polygon(c).buffer(0); g = p if g is None else g.symmetric_difference(p)
    if g is None: return []
    ps = [g] if g.geom_type == 'Polygon' else list(g.geoms)
    return sorted((round(Polygon(r).area) for p in ps for r in p.interiors), reverse=True)
R = TTFont(os.path.join(ROOT, 'reference', 'Faruma.ttf')); N = TTFont(sys.argv[1])
for n in ['uni0784', 'uni0788', 'uni078C', 'uni0793', 'uni0797', 'uni07B0', 'uni0789', 'uni0798', 'uni07A0', 'uni07A5']:
    print(f'{n:9s} ref {holes(R, n)}  new {holes(N, n)}')
