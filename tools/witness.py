"""Witness strings from the reviews: minimum ink gap between DIFFERENT glyphs (or named components) in
each shaped string, reference vs candidate.  usage: witness.py [font.ttf]"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from shapely.geometry import Polygon
from shapely import affinity
from raster import contours
NEW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build', 'wip.ttf')
REF = os.path.join(ROOT, 'reference', 'Faruma.ttf')
W = ['ހޮޥާ', 'ހޮޕޯ', 'ޥޫޥޯ', 'ދޓ', 'ޛޓ', 'ލޓ', 'ދޱ', 'ޛޱ', 'ތޱ', 'ހޫ', 'ޖީ', 'ޘް', 'ޘޯ', 'ޤޯ', 'ޗޮ', 'ޗޭ', 'ހޮހޯ', 'ދޖ', 'ޛޖ', 'ހޯޥޫ', 'ފޥީ', 'ޕޥީ', 'ދޒ', 'ޛޒ', 'ހޫޥޫ', 'ހޭޥޮ', 'ހޮޥޮ', 'ހޭޥޯ', 'ހޭޱޯ', 'ހޭޗ']
def loader(path, comps=False):
    tt = TTFont(path); order = tt.getGlyphOrder(); font = hb.Font(hb.Face(hb.Blob.from_file_path(path))); cache = {}
    def geom(n):
        if n not in cache:
            g = None
            for c in contours(tt, n):
                if len(c) < 3: continue
                p = Polygon(c).buffer(0); g = p if g is None else g.symmetric_difference(p)
            cache[n] = g
        return cache[n]
    def run(t):
        buf = hb.Buffer(); buf.add_str(t); buf.guess_segment_properties(); hb.shape(font, buf, {})
        x = 0; parts = []
        for i, p in zip(buf.glyph_infos, buf.glyph_positions):
            n = order[i.codepoint]; g = geom(n)
            if g is not None: parts.append((n, affinity.translate(g, x + p.x_offset, p.y_offset)))
            x += p.x_advance
        best = None
        for i in range(len(parts)):
            for j in range(i + 1, len(parts)):
                a, b = parts[i][1], parts[j][1]
                d = -round(a.intersection(b).area ** .5) if a.intersects(b) else round(a.distance(b))
                if best is None or d < best[0]: best = (d, parts[i][0] + '/' + parts[j][0])
        return best or (None, '')
    return run
def ttaa_internal(path, gname='uni0798'):  # built-in mark vs base inside a composite
    tt = TTFont(path); g = tt['glyf'][gname]
    gs = tt.getGlyphSet(); from raster import FlatPen
    geo = []
    for comp in g.components:
        pen = FlatPen(gs); gs[comp.glyphName].draw(pen); gg = None
        for c in pen.contours:
            p = Polygon(c).buffer(0); gg = p if gg is None else gg.symmetric_difference(p)
        geo.append(affinity.translate(gg, comp.x, comp.y))
    a, b = geo
    return -round(a.intersection(b).area ** .5) if a.intersects(b) else round(a.distance(b))
R, N = loader(REF), loader(NEW)
print(f"{'string':10s} {'ref':>6s} {'new':>6s}")
for w in W:
    r, n = R(w), N(w)
    print(f'{w:10s} {str(r[0]):>6s} {str(n[0]):>6s}   new worst pair: {n[1]}')
print(f"{'ޘ caret↔bowl':10s} {ttaa_internal(REF):6d} {ttaa_internal(NEW):6d}")
print(f"{'ޢ dot↔foot':10s} {ttaa_internal(REF, 'uni07A2'):6d} {ttaa_internal(NEW, 'uni07A2'):6d}")
