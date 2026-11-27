"""Adjacent-cluster clearance: fili of one cluster vs ink of the neighbouring cluster (both directions),
shaped with HarfBuzz exactly as in running text. Compares candidate with the reference.
usage: clearance_adj.py [font.ttf]"""
import sys, os, itertools
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely import affinity
from raster import contours
NEW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build', 'wip.ttf')
REF = os.path.join(ROOT, 'reference', 'Faruma.ttf')
BASES = [chr(c) for c in range(0x780, 0x7A6)]
FILI = [chr(c) for c in range(0x7A6, 0x7B1)]

def loader(path):
    tt = TTFont(path); order = tt.getGlyphOrder(); cache = {}
    font = hb.Font(hb.Face(hb.Blob.from_file_path(path)))
    def geom(n):
        if n not in cache:
            g = None
            for c in contours(tt, n):
                if len(c) < 3: continue
                p = Polygon(c).buffer(0); g = p if g is None else g.symmetric_difference(p)
            cache[n] = g
        return cache[n]
    def measure(c1, c2):
        buf = hb.Buffer(); buf.add_str(c1 + c2); buf.guess_segment_properties(); hb.shape(font, buf, {})
        x = 0; parts = {1: [], 2: []}; marks = {1: [], 2: []}
        for i, p in zip(buf.glyph_infos, buf.glyph_positions):
            n = order[i.codepoint]; g = geom(n); k = 1 if i.cluster < len(c1) else 2
            if g is not None:
                gg = affinity.translate(g, x + p.x_offset, p.y_offset)
                parts[k].append(gg)
                if n.endswith('nsp'): marks[k].append(gg)
            x += p.x_advance
        res = []
        for a, b in ((1, 2), (2, 1)):
            if marks[a] and parts[b]:
                m = unary_union(marks[a]); o = unary_union(parts[b])
                res.append(-round(m.intersection(o).area ** 0.5) if m.intersects(o) else round(m.distance(o)))
        return min(res) if res else None
    return measure

R, N = loader(REF), loader(NEW)
cases = []
for b1, b2 in itertools.product(BASES, BASES):
    for f in FILI:
        cases.append((b1 + f, b2)); cases.append((b1, b2 + f))
for b2 in BASES:
    for f1, f2 in itertools.product(FILI, FILI):
        cases.append(('ހ' + f1, b2 + f2))
bad = []; worse = 0; n_ov = r_ov = 0
for c1, c2 in cases:
    n = N(c1, c2)
    if n is None or n >= 40: continue
    r = R(c1, c2)
    if n < 0: n_ov += 1
    if r is not None and r < 0: r_ov += 1
    if n < 0 and (r is None or r >= 0 or n < r - 20): bad.append((c1 + c2, r, n))
print(f'{len(cases)} adjacent-cluster cases; candidate overlaps(<0) among tight cases: {n_ov}; reference overlaps there: {r_ov}')
print(f'candidate overlaps where the reference is clear or better: {len(bad)}')
for t in sorted(bad, key=lambda x: x[2])[:40]: print('  ', ' '.join(f'U+{ord(ch):04X}' for ch in t[0]), t[0], 'ref', t[1], 'new', t[2])
