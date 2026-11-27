import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools')); sys.path.insert(0, os.path.join(ROOT, 'src'))
import importlib, stroke, thaana
from shapely.geometry import Polygon
def holes(n):
    importlib.reload(thaana)
    cs = stroke.finalize(thaana.GLYPHS[n]())
    out = []
    for c in cs:
        p = Polygon(c)
        if p.exterior.is_ccw: out.append(round(p.area))  # holes are CCW in TrueType orientation
    return sorted(out, reverse=True)
if __name__ == '__main__':
    for n in sys.argv[1].split(','): print(n, holes(n))
