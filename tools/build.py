"""Build the font: original Thaana outlines (src/thaana.py) + Liberation Serif Latin (OFL)
with the reference font's functional metrics (spec/metrics.json).

usage: python tools/build.py [out.ttf]
"""
import sys, os, json, importlib

for _s in (sys.stdout, sys.stderr):   # diagnostics never fail on a non-UTF-8 console: unencodable text is escaped
    try: _s.reconfigure(errors='backslashreplace')
    except Exception: pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); sys.path.insert(0, os.path.join(ROOT, 'src'))
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
import stroke
try:
    from fitcurves import draw_fitted
except Exception:  # fallback: straight segments
    draw_fitted = None

FAMILY = os.environ.get('FONT_FAMILY', 'Rasmee Thaana')
VERSION = os.environ.get('FONT_VERSION', '1.007')
M = json.load(open(os.path.join(ROOT, 'spec', 'metrics.json'), encoding='utf-8'))
LATIN = os.path.join(ROOT, 'latin', 'liberation-fonts-ttf-2.1.5', 'LiberationSerif-Regular.ttf')

import thaana
importlib.reload(thaana)
AMIRI = os.path.join(ROOT, 'latin', 'Amiri-1.003', 'Amiri-Regular.ttf')
AMIRI_BOLD = os.path.join(ROOT, 'latin', 'Amiri-1.003', 'Amiri-Bold.ttf')
# Glyphs taken from OFL fonts and fitted (uniform scale) into the reference bounding box.
LIB = LATIN
# Glyphs taken from OFL fonts (optionally transformed: rotate/mirror) and fitted (uniform scale)
# into the reference bounding box. Each entry: list of (font, source glyph, affine 2x2+offset).
ROT180 = (-1, 0, 0, -1, 0, 0); MIRROR = (-1, 0, 0, 1, 0, 0); ID = (1, 0, 0, 1, 0, 0)
EXTERNAL = {
    # legacy Thaana keyboard: ` -> Bismillah, one calligraphic line (Amiri Bold, OFL) like the reference
    'grave': [(AMIRI_BOLD, 'SHAPE:بســم الله الرحمٰن الرحيم', ID)],
    'endash': [(LIB, 'endash', ID)], 'emdash': [(LIB, 'emdash', ID)],
    'bullet': [(LIB, 'bullet', ID)], 'uni00B7': [(LIB, 'periodcentered', ID)],
    # Thaana conventions of the reference: full stop sits at mid-height, underscore clears the lower fili
    'period': [(LIB, 'period', ID)], 'underscore': [(LIB, 'underscore', ID)],
}
STRETCH = {'endash', 'emdash', 'underscore'}
# optical widening after the uniform fit (clamped to the reference box width)
WIDEN = {}
# embolden imported calligraphy (units of outline offset) toward the reference's ink
EMBOLDEN = {'grave': 11}
THIN = {}
MARKSCALE = {}
# (the Allah ligature uniFDF2 is drawn natively in src/thaana.py)
COMPOSE = {}
APERTURE = {'grave': [(3455, 413, 18)]}
# (x0, x1, y_base, y_top_of_lift_ramp, lift) in final glyph units
LIFT = {}
# vertical emphasis of the shaped Bismillah (alif/lam ascenders lengthen naturally in calligraphy)
HEIGHTEN = {'grave': 1.46}
# rising sweep of the elongated first word: (fraction of line width from the right, lift in source units)
RISE = {'grave': (0.3, 230)}
# Legacy mapping in the reference: [ ] draw as quotation marks.
ALIAS = {'bracketleft': 'quotedblleft', 'bracketright': 'quotedblright'}
_ext_cache = {}
CONTROLS = ('uni200C', 'uni200D', 'uni200E', 'uni200F')
LIBNAME = {}  # extra CP1252 glyphs -> Liberation source glyph


from fontTools.pens.filterPen import FilterPen


class DedupePen(FilterPen):
    """Round to integer font units and drop repeated / zero-length points inside segments."""
    def __init__(self, out):
        super().__init__(out); self.cur = None
    def _r(self, p): return (round(p[0]), round(p[1])) if p is not None else None
    def moveTo(self, p):
        self.cur = self._r(p); self._outPen.moveTo(self.cur)
    def lineTo(self, p):
        q = self._r(p)
        if q != self.cur: self._outPen.lineTo(q); self.cur = q
    def qCurveTo(self, *ps):
        pts = [self._r(p) for p in ps]
        on = pts[-1]; offs = []
        prev = self.cur
        for q in pts[:-1]:
            if q is None or q == prev or (offs and q == offs[-1]): continue
            offs.append(q)
        if on is None:
            if offs: self._outPen.qCurveTo(*offs, None)
            return
        offs = [q for q in offs if q != on]
        if on == self.cur and not offs: return
        if offs: self._outPen.qCurveTo(*offs, on)
        else: self._outPen.lineTo(on)
        self.cur = on
    def curveTo(self, *ps):
        self._outPen.curveTo(*[self._r(p) for p in ps]); self.cur = self._r(ps[-1])
    def closePath(self): self._outPen.closePath(); self.cur = None
    def endPath(self): self._outPen.endPath(); self.cur = None


def _compose(geo, spec):
    """Lay out the components of an imported ligature into target boxes (layout only; shapes kept).
    spec: dict role -> target box; roles: body (largest), alif (rightmost tall), shadda, dagger (marks,
    lower/upper). Optional 'ramp': (y_base, x_left, k_left, x_right, k_right) height ramp on the body."""
    from shapely import affinity as _af
    from shapely.ops import unary_union as _uu2
    parts = list(geo.geoms) if geo.geom_type != 'Polygon' else [geo]
    parts = [q for q in parts if q.area > 200]
    body = max(parts, key=lambda q: q.area)
    rest = [q for q in parts if q is not body]
    alif = max(rest, key=lambda q: q.bounds[2])
    marks = sorted([q for q in rest if q is not alif], key=lambda q: q.bounds[1])
    def fit(q, box, uniform=False):
        x0, y0, x1, y1 = q.bounds; bx0, by0, bx1, by1 = box
        sx = (bx1 - bx0) / (x1 - x0); sy = (by1 - by0) / (y1 - y0)
        if uniform: sx = sy = min(sx, sy)
        q = _af.scale(q, sx, sy, origin=(x0, y0))
        x0, y0, x1, y1 = q.bounds
        return _af.translate(q, (bx0 + bx1) / 2 - (x0 + x1) / 2, (by0 + by1) / 2 - (y0 + y1) / 2)
    out = []
    b = fit(body, spec['body'])
    if 'ramp' in spec:
        yb, xl, kl, xr, kr = spec['ramp']
        def warp(x, y, z=None):
            t = min(1.0, max(0.0, (x - xl) / (xr - xl))); k = kl + (kr - kl) * t
            return (x, y if y <= yb else yb + (y - yb) * k)
        from shapely.ops import transform as _tr
        b = _tr(lambda xs, ys, zs=None: tuple(zip(*[warp(x, y) for x, y in zip(xs, ys)])) if hasattr(xs, '__len__') else warp(xs, ys), b)
        b = fit(b, spec['body'])
    if spec.get('fill_body_holes'):   # solid descending hā sweep (no closed loop), like the reference
        from shapely.geometry import Polygon as _Pg
        bx0w = spec['fill_body_holes']
        polys = list(b.geoms) if b.geom_type != 'Polygon' else [b]
        b = _uu2([_Pg(p.exterior.coords, [h for h in p.interiors if _Pg(h).centroid.x > bx0w]) for p in polys])
    eb = spec.get('body_offset', 0)
    out.append(b.buffer(eb, join_style=1) if eb else b)
    al = fit(alif, spec['alif']); ao = spec.get('alif_offset', eb)
    out.append(al.buffer(ao, join_style=1) if ao else al)
    if len(marks) >= 2:
        mo = spec.get('mark_offset', 0)
        for q, key in ((marks[0], 'shadda'), (marks[-1], 'dagger')):
            bx = spec[key]; m = mo if key == 'shadda' else mo // 3
            q = fit(q, (bx[0] + m, bx[1] + m, bx[2] - m, bx[3] - m), uniform=(key == 'shadda' and not spec.get('shadda_stretch')))
            out.append(q.buffer(m, join_style=1) if m else q)
        out += marks[1:-1]
    else:
        out += marks
    return _uu2(out)


def draw_external(pen, name):
    from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen
    from fontTools.pens.boundsPen import BoundsPen
    rec_all = RecordingPen()
    for path, src, mat in EXTERNAL[name]:
        if path not in _ext_cache: _ext_cache[path] = TTFont(path)
        f = _ext_cache[path]; gs = f.getGlyphSet()
        if src.startswith('SHAPE:'):
            # shape a phrase with HarfBuzz and collect its outlines (compact word spacing)
            import uharfbuzz as hb
            from fontTools.pens.boundsPen import BoundsPen as _BP
            face = hb.Face(hb.Blob.from_file_path(path)); hf = hb.Font(face)
            buf = hb.Buffer(); buf.add_str(src[6:]); buf.guess_segment_properties(); hb.shape(hf, buf, {})
            go = f.getGlyphOrder(); x = 0; space = f.getBestCmap()[0x20]
            line = RecordingPen()
            for gi, gp in zip(buf.glyph_infos, buf.glyph_positions):
                gname = go[gi.codepoint]
                rec = DecomposingRecordingPen(gs); gs[gname].draw(rec)
                rec.replay(TransformPen(line, (1, 0, 0, 1, x + gp.x_offset, gp.y_offset)))
                x += gp.x_advance * (0.2 if gname == space else 1.0)
            if name in RISE:
                # rising sweep: lift the first word (rightmost in visual order) progressively toward the right
                from fontTools.pens.filterPen import FilterPen
                from fontTools.pens.boundsPen import BoundsPen as _BP2
                bpl = _BP2(None); line.replay(bpl); lx0, _, lx1, _ = bpl.bounds
                x0r = lx1 - RISE[name][0] * (lx1 - lx0); lift = RISE[name][1]
                class _Warp(FilterPen):
                    def _w(self, p):
                        x, y = p; t = max(0.0, (x - x0r) / (lx1 - x0r))
                        return (x, y + lift * (t * t * (3 - 2 * t)))
                    def moveTo(self, p): self._outPen.moveTo(self._w(p))
                    def lineTo(self, p): self._outPen.lineTo(self._w(p))
                    def curveTo(self, *ps): self._outPen.curveTo(*[self._w(p) for p in ps])
                    def qCurveTo(self, *ps): self._outPen.qCurveTo(*[self._w(p) if p is not None else None for p in ps])
                warped = RecordingPen(); line.replay(_Warp(warped)); line = warped
            if isinstance(mat, tuple) and mat and mat[0] == 'STACK':
                # place this tier above-right of the tier recorded so far
                bp0 = _BP(None); rec_all.replay(bp0); bp1 = _BP(None); line.replay(bp1)
                ax1 = bp0.bounds[2]; bx0, _, bx1, _ = bp1.bounds
                dx_ = ax1 - bx1 + mat[1] * (bx1 - bx0)
                line.replay(TransformPen(rec_all, (1, 0, 0, 1, dx_, mat[2])))
            else:
                line.replay(rec_all)
            continue
        rec = DecomposingRecordingPen(gs); gs[src].draw(rec)
        rec.replay(TransformPen(rec_all, mat))
    bp = BoundsPen(None); rec_all.replay(bp); x0, y0, x1, y1 = bp.bounds
    tx0, ty0, tx1, ty1 = M['glyphs'][name]['bbox']
    sc = min((tx1 - tx0) / (x1 - x0), (ty1 - ty0) / (y1 - y0))
    dx = (tx0 + tx1) / 2 - sc * (x0 + x1) / 2; dy = (ty0 + ty1) / 2 - sc * (y0 + y1) / 2
    sx = sy = sc
    if name in WIDEN:
        sx = min(sc * WIDEN[name], (tx1 - tx0) / (x1 - x0))
        dx = (tx0 + tx1) / 2 - sx * (x0 + x1) / 2
    if name in HEIGHTEN:
        sy = min(sc * HEIGHTEN[name], (ty1 - ty0) / (y1 - y0))
        dy = (ty0 + ty1) / 2 - sy * (y0 + y1) / 2
    if name in STRETCH:  # simple geometric marks (dashes, bullets) take the reference box exactly
        sx = (tx1 - tx0) / (x1 - x0); sy = (ty1 - ty0) / (y1 - y0)
        dx = (tx0 + tx1) / 2 - sx * (x0 + x1) / 2; dy = (ty0 + ty1) / 2 - sy * (y0 + y1) / 2
    # remove overlaps / fix direction with Skia pathops, then draw (TrueType clockwise)
    import pathops
    path = pathops.Path(); pp = pathops.PathPen(path)
    if name in LIFT:
        # local smooth lifts in final coordinates (e.g. taller lams / alif), then refit into the reference box
        from fontTools.pens.filterPen import FilterPen as _FP
        def _w(p):
            if p is None: return None
            x, y = p; y2 = y
            for (x0w, x1w, yb, yt, lift) in LIFT[name]:
                fx = 1.0 if x0w <= x <= x1w else max(0.0, 1 - min(abs(x - x0w), abs(x - x1w)) / 80.0)
                t = min(1.0, max(0.0, (y - yb) / (yt - yb))); t = t * t * (3 - 2 * t)
                y2 += fx * lift * t
            return (x, y2)
        class _WP(_FP):
            def moveTo(self, p): self._outPen.moveTo(_w(p))
            def lineTo(self, p): self._outPen.lineTo(_w(p))
            def curveTo(self, *ps): self._outPen.curveTo(*[_w(p) for p in ps])
            def qCurveTo(self, *ps): self._outPen.qCurveTo(*[_w(p) if p is not None else None for p in ps])
        warped = RecordingPen(); rec_all.replay(TransformPen(_WP(warped), (sx, 0, 0, sy, dx, dy)))
        bpw = BoundsPen(None); warped.replay(bpw); wx0, wy0, wx1, wy1 = bpw.bounds
        k = min((tx1 - tx0) / (wx1 - wx0), (ty1 - ty0) / (wy1 - wy0))
        warped.replay(TransformPen(pp, (k, 0, 0, k, (tx0 + tx1) / 2 - k * (wx0 + wx1) / 2, (ty0 + ty1) / 2 - k * (wy0 + wy1) / 2)))
    else:
        rec_all.replay(TransformPen(pp, (sx, 0, 0, sy, dx, dy)))
    path.simplify(fix_winding=True, keep_starting_points=False, clockwise=True)
    from fontTools.pens.cu2quPen import Cu2QuPen
    if name in EMBOLDEN:
        # outline offset via shapely, then redraw through the curve fitter
        from raster import FlatPen
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        fp = FlatPen(None, steps=10); path.draw(fp)
        geo = None
        for c in fp.contours:
            if len(c) < 3: continue
            pg = Polygon(c).buffer(0); geo = pg if geo is None else geo.symmetric_difference(pg)
        if EMBOLDEN[name]:
            geo = geo.buffer(EMBOLDEN[name], join_style=1)
        for (rx0, ry0, rx1, ry1, rd) in THIN.get(name, []):  # lighten marks inside a zone
            from shapely.geometry import box as _bx
            zone = _bx(rx0, ry0, rx1, ry1)
            geo = geo.difference(zone).union(geo.intersection(zone).buffer(-rd, join_style=1)).buffer(0)
        if name in COMPOSE:
            geo = _compose(geo, COMPOSE[name])
        if name in MARKSCALE:
            # shrink the free marks (components wholly above y_cut) about their own centres, then refit
            from shapely import affinity as _af
            from shapely.ops import unary_union as _uu2
            ycut, k, mdy = MARKSCALE[name]
            parts = list(geo.geoms) if geo.geom_type != 'Polygon' else [geo]
            parts = [(_af.translate(_af.scale(q, k, k, origin='centroid'), 0, mdy) if q.bounds[1] > ycut else q) for q in parts]
            geo = _uu2(parts)
            gx0, gy0, gx1, gy1 = geo.bounds
            kk = min((tx1 - tx0) / (gx1 - gx0), (ty1 - ty0) / (gy1 - gy0))
            geo = _af.scale(geo, kk, kk, origin=(0, 0))
            gx0, gy0, gx1, gy1 = geo.bounds
            geo = _af.translate(geo, (tx0 + tx1) / 2 - (gx0 + gx1) / 2, (ty0 + ty1) / 2 - (gy0 + gy1) / 2)
        for (ax, ay, ar) in APERTURE.get(name, []):  # re-open counters closed by emboldening
            from shapely.geometry import Point
            geo = geo.difference(Point(ax, ay).buffer(ar))
        draw_contours(pen, stroke.finalize([geo], simplify=0.4))
        return
    path.draw(Cu2QuPen(DedupePen(pen), max_err=1.0, reverse_direction=False))


ANALYTIC_DOTS = {'DotAbove', 'DotBelow', 'TwoDots', 'uni25CC'}


def draw_analytic_dots(pen, contours):
    """Redraw each (convex, dot-like) contour as a compact 8-arc all-off-curve quadratic ellipse
    with the same centre, axes and orientation (clockwise, TrueType outer contour)."""
    import numpy as np, math
    for c in contours:
        P = np.array(c, float); cx, cy = P.mean(axis=0)
        Q = P - [cx, cy]
        w, V = np.linalg.eigh(np.cov(Q.T)); ax = V[:, 1]; ang = math.atan2(ax[1], ax[0])
        R = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
        L = Q @ R  # coordinates along (major, minor)
        a = np.abs(L[:, 0]).max(); b = np.abs(L[:, 1]).max()
        # area-preserving radii for the drawn ellipse
        from shapely.geometry import Polygon
        area = abs(Polygon(c).area); k = math.sqrt(area / (math.pi * a * b)); a *= k; b *= k
        s = 1 / math.cos(math.pi / 8)
        pts = []
        for i in range(8):
            t = -i * math.pi / 4  # clockwise
            x, y = a * s * math.cos(t), b * s * math.sin(t)
            X, Y = R @ [x, y]
            pts.append((round(cx + X), round(cy + Y)))
        pen.qCurveTo(*pts, None)
        pen.closePath()


def _flatten_rec(rec):
    """Flatten a RecordingPen (lines + quadratic splines) into one polygon point list."""
    from fontTools.pens.basePen import decomposeQuadraticSegment
    pts = []
    for op, args in rec.value:
        if op == 'moveTo':
            pts = [args[0]]
        elif op == 'lineTo':
            pts.append(args[0])
        elif op == 'qCurveTo':
            for (c, e) in decomposeQuadraticSegment(list(args)):
                s0 = pts[-1]
                for k in range(1, 9):
                    t = k / 8
                    pts.append(((1 - t) ** 2 * s0[0] + 2 * t * (1 - t) * c[0] + t * t * e[0],
                                (1 - t) ** 2 * s0[1] + 2 * t * (1 - t) * c[1] + t * t * e[1]))
    return pts


def draw_contours(pen, contours):
    if draw_fitted:
        # fit each contour; reject a fit whose flattened outline self-intersects (tighter refits, then polyline)
        from fontTools.pens.recordingPen import RecordingPen
        from shapely.geometry import Polygon as _SP
        for c in contours:
            done = False
            for tol in (1.2, 0.8, 0.5, 0.3):
                rec = RecordingPen(); draw_fitted(rec, [c], tol=tol)
                if not rec.value:
                    done = True; break
                fl = _flatten_rec(rec)
                if len(fl) >= 3 and _SP(fl).is_valid:
                    rec.replay(pen); done = True
                    if tol != 1.2: print('  refit contour at tol', tol)
                    break
            if not done:
                print('  polyline fallback for a contour')
                pts = [(round(x), round(y)) for x, y in c]
                ded = [pts[0]] + [p for a, p in zip(pts, pts[1:]) if p != a]
                pen.moveTo(ded[0]); [pen.lineTo(p) for p in ded[1:]]; pen.closePath()
        return
    for c in contours:
        pts = [(round(x), round(y)) for x, y in c]
        ded = [pts[0]] + [p for a, p in zip(pts, pts[1:]) if p != a]
        if len(ded) < 3:
            continue
        pen.moveTo(ded[0])
        for p in ded[1:]:
            pen.lineTo(p)
        pen.closePath()


def build(out):
    order = list(M['glyphs'].keys())
    cmap = {int(k, 16): v for k, v in M['cmap'].items()}
    cmap.setdefault(0x00A0, 'space')  # NBSP -> space
    lat0 = TTFont(LATIN); lc0 = lat0.getBestCmap()
    extra_latin = []
    for b in range(0x20, 0x100):
        try: ch = bytes([b]).decode('cp1252')
        except UnicodeDecodeError: continue
        cp = ord(ch)
        if cp in cmap or cp < 0x20 or cp not in lc0: continue
        gname = lc0[cp]
        if gname in M['glyphs'] or gname in order: gname = gname + '.lib'
        order.append(gname); cmap[cp] = gname; extra_latin.append(gname)
        M['glyphs'][gname] = {'adv': lat0['hmtx'][lc0[cp]][0], 'lsb': 0, 'bbox': None}
        LIBNAME[gname] = lc0[cp]
    order.append('uniFDFD'); cmap[0xFDFD] = 'uniFDFD'  # own glyph ID (composite of the legacy one)
    M['glyphs']['uniFDFD'] = {'adv': M['glyphs']['grave']['adv'], 'lsb': 0, 'bbox': None}
    M['composites']['uniFDFD'] = [['grave', 0, 0]]
    for cp in (0x200C, 0x200D, 0x200E, 0x200F):  # ZWNJ, ZWJ, LRM, RLM: zero-width, no ink
        order.append(f'uni{cp:04X}'); cmap[cp] = f'uni{cp:04X}'
        M['glyphs'][f'uni{cp:04X}'] = {'adv': 0, 'lsb': 0, 'bbox': None}
    lat = TTFont(LATIN); lgs = lat.getGlyphSet(); lcmap = lat.getBestCmap()

    rev = {}
    for k, v in sorted(cmap.items()): rev.setdefault(v, k)
    glyphs, metrics = {}, {}
    # 1) original Thaana & symbol outlines
    defs = thaana.GLYPHS
    for name in order:
        adv = M['glyphs'][name]['adv']
        if name in M['composites'] and name not in defs:
            g = Glyph(); g.components = []
            for (base, x, y) in M['composites'][name]:
                c = GlyphComponent(); c.glyphName = base; c.x = x; c.y = y; c.flags = 0
                g.components.append(c)
            g.numberOfContours = -1
            glyphs[name] = g; metrics[name] = (adv, 0)
            continue
        pen = TTGlyphPen(None)
        if name in CONTROLS or name in ('space', 'nonmarkingreturn', 'NULL'):
            glyphs[name] = pen.glyph(); metrics[name] = (adv, 0)
            continue
        if name in defs:
            geoms = defs[name]() if callable(defs[name]) else defs[name]
            if name in ANALYTIC_DOTS:
                draw_analytic_dots(pen, stroke.finalize(geoms))
            else:
                draw_contours(pen, stroke.finalize(geoms))
        elif name in EXTERNAL:
            draw_external(pen, name)
        elif name in LIBNAME or name in ALIAS or (name in rev and (rev[name] in lcmap)):
            lname = LIBNAME[name] if name in LIBNAME else (lcmap[rev[ALIAS[name]]] if name in ALIAS else lcmap[rev[name]])
            ladv = lat['hmtx'][lname][0]
            dx = (adv - ladv) / 2.0  # centre Latin glyph if advance differs
            from fontTools.pens.recordingPen import DecomposingRecordingPen
            rec = DecomposingRecordingPen(lgs); lgs[lname].draw(rec)
            rec.replay(TransformPen(pen, (1, 0, 0, 1, dx, 0)))
        elif name == '.notdef':
            for c in [[(256, 0), (256, 1536), (1792, 1536), (1792, 0)], [(384, 128), (1664, 128), (1664, 1408), (384, 1408)]]:
                pen.moveTo(c[0]); [pen.lineTo(p) for p in c[1:]]; pen.closePath()
        glyphs[name] = pen.glyph(); metrics[name] = (adv, 0)

    fb = FontBuilder(M['upm'], isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    gt = fb.font['glyf']
    for n in order:
        gt[n].recalcBounds(gt)
        metrics[n] = (metrics[n][0], getattr(gt[n], 'xMin', 0) if gt[n].numberOfContours else 0)
    fb.setupHorizontalMetrics(metrics)
    # guard: every mapped graphic character must have ink; format controls must have none
    from fontTools.pens.boundsPen import BoundsPen
    gs = fb.font.getGlyphSet()
    for cp, n in cmap.items():
        bp = BoundsPen(gs); gs[n].draw(bp)
        if n in CONTROLS:
            assert bp.bounds is None and metrics[n][0] == 0, f'{n} must be blank zero-width'
        elif cp not in (0x20, 0xA0) and bp.bounds is None:
            raise SystemExit(f'empty glyph for mapped U+{cp:04X} ({n})')
    v = M['vertical']
    fb.setupHorizontalHeader(ascent=v['hhea_ascent'], descent=v['hhea_descent'], lineGap=v['hhea_lineGap'])
    fb.setupNameTable({
        'copyright': f'Copyright 2026 The {FAMILY} Project Authors. Latin: Digitized data copyright (c) 2010 Google Corporation. Copyright (c) 2012 Red Hat, Inc. Arabic ligatures: Copyright 2010-2022 The Amiri Project Authors (https://github.com/aliftype/amiri).',
        'familyName': FAMILY, 'styleName': 'Regular',
        'uniqueFontIdentifier': f'{FAMILY.replace(" ", "")}-Regular;{VERSION}',
        'fullName': f'{FAMILY} Regular', 'psName': f'{FAMILY.replace(" ", "")}-Regular',
        'version': f'Version {VERSION}',
        'description': 'Original Thaana typeface with metrics compatible with the de-facto Maldivian standard text face.',
        'licenseDescription': open(os.path.join(ROOT, 'OFL.txt'), encoding='utf-8').read(),
        'designer': f'{FAMILY} Project Authors',
        'licenseInfoURL': 'https://openfontlicense.org',
    })
    fb.setupOS2(sTypoAscender=v['typoAscender'], sTypoDescender=v['typoDescender'], sTypoLineGap=v['typoLineGap'],
                usWinAscent=v['winAscent'], usWinDescent=v['winDescent'], sxHeight=940, sCapHeight=1341,
                ySubscriptXSize=1434, ySubscriptYSize=1331, ySubscriptYOffset=293, ySuperscriptXSize=1434, ySuperscriptYSize=1331, ySuperscriptYOffset=928,
                usWeightClass=400, usWidthClass=5, fsType=0, achVendID='NONE',
                yStrikeoutSize=v['strikeoutSize'], yStrikeoutPosition=v['strikeoutPosition'],
                ulCodePageRange1=(1 << 0),
                fsSelection=0x40)
    fb.font['OS/2'].recalcUnicodeRanges(fb.font)
    o2 = fb.font['OS/2']; assert o2.ulUnicodeRange3 & (1 << 8), 'Thaana bit 72 must be set'
    fb.setupPost(underlinePosition=v['underlinePosition'], underlineThickness=v['underlineThickness'])
    from fontTools.misc.timeTools import timestampNow
    from fontTools.misc.timeTools import timestampSinceEpoch
    _ts = timestampSinceEpoch(int(os.environ.get('SOURCE_DATE_EPOCH', '1795737600')))  # reproducible: 2026-11-27 UTC
    fb.setupHead(unitsPerEm=M['upm'], fontRevision=float(VERSION), created=_ts, modified=_ts)

    # OpenType layout: ccmp (fili -> zero-width marks), mark classes, kerning (reference values)
    fili = ['uni07A6', 'uni07A7', 'uni07A8', 'uni07A9', 'uni07AA', 'uni07AB', 'uni07AC', 'uni07AD', 'uni07AE', 'uni07AF', 'uni07B0']
    bases = [n for n in order if n.startswith('uni07') and n not in fili and not n.endswith('nsp')]
    marks = [f + 'nsp' for f in fili]
    lower = ['uni07A8nsp', 'uni07A9nsp']; upper = [m for m in marks if m not in lower]
    kern_lines = '\n'.join(f'  pos {a} {b} {v};' for a, b, v in M['gpos_kern'])
    lat_kern = '\n'.join(f'  pos {a} {b} {v};' for a, b, v in M['kern'] if not a.startswith('uni07'))
    fea = f"""
languagesystem DFLT dflt;
languagesystem thaa dflt;
languagesystem latn dflt;
@FILI = [{' '.join(fili)}];
@FILI_NSP = [{' '.join(marks)}];
table GDEF {{
  GlyphClassDef [{' '.join(bases + ['uni25CC'])}], , [{' '.join(marks + fili)}], ;
}} GDEF;
feature ccmp {{
  script thaa;
  sub @FILI by @FILI_NSP;
}} ccmp;
lookup THAANA_KERN {{
{kern_lines}
}} THAANA_KERN;
feature kern {{
  script thaa; lookup THAANA_KERN;
}} kern;
markClass [{' '.join(upper)}] <anchor 0 0> @FILI_UP;
markClass [{' '.join(lower)}] <anchor 0 0> @FILI_LO;
feature mark {{
  script thaa;
  # explicit mark-to-base attachment (Uniscribe/DirectWrite); zero anchors keep the reference positions,
  # the dotted-circle carrier lifts upper fili clear of its ring
  pos base [{' '.join(bases)}] <anchor 0 0> mark @FILI_UP <anchor 0 0> mark @FILI_LO;
  pos base uni25CC <anchor 0 175> mark @FILI_UP <anchor 0 0> mark @FILI_LO;
}} mark;
"""
    addOpenTypeFeaturesFromString(fb.font, fea)
    # legacy 'kern' table (format 0) for older applications, same values as reference
    from fontTools.ttLib.tables._k_e_r_n import KernTable_format_0
    kt = newTable('kern'); kt.version = 0; st = KernTable_format_0(); st.coverage = 1; st.version = 0; st.format = 0
    st.kernTable = {(a, b): v for a, b, v in M['kern']}
    kt.kernTables = [st]; fb.font['kern'] = kt
    fb.font['gasp'] = newTable('gasp'); fb.font['gasp'].gaspRange = {8: 0x000A, 0xFFFF: 0x000F}
    fb.font['head'].lowestRecPPEM = 9
    fb.font.recalcTimestamp = False
    fb.save(out)
    # reopen to normalise / recompute (timestamps stay at the reproducible release date)
    f = TTFont(out, recalcTimestamp=False); f.save(out)
    if os.environ.get('NO_HINT') != '1':
        # TrueType hinting: Latin via ttfautohint 'latn'; Thaana left unhinted (fallback 'none') so its
        # shapes are only scaled, never snapped to Latin blue zones. Windows-compatible vertical metrics.
        import ttfautohint, shutil
        tmp = out + '.tmp'
        ttfautohint.ttfautohint(in_file=out, out_file=tmp, default_script='latn', fallback_script='none', fallback_scaling=True,
                                hinting_range_min=8, hinting_range_max=50, no_info=True, windows_compatibility=True)
        shutil.move(tmp, out)
        f = TTFont(out, recalcTimestamp=False); f['head'].modified = f['head'].created = _ts
        f['gasp'].gaspRange = {8: 0x000A, 0xFFFF: 0x000F}; f.save(out)
    print('built', out)


def main():
    """Build into a unique temporary sibling file, validate it, then install it atomically (mode 0644).
    If the destination currently holds the approved release (its SHA-256 equals spec/release_baseline.json's
    font_sha256) and the new build differs, the destination is left unchanged unless --replace-approved is given."""
    import tempfile, hashlib, json, argparse, re
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from font_checks import strict_parser, validate_sfnt, FontInvalid
    ap = strict_parser('build.py'); ap.add_argument('out', nargs='?', default=os.path.join(ROOT, 'build', 'RasmeeThaana-Regular.ttf'))
    ap.add_argument('--replace-approved', action='store_true', help='allow replacing a file that holds the approved release')
    a = ap.parse_args(); out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
    if os.path.isdir(out):
        print(f'FAIL: output path {out} is a directory; nothing built'); sys.exit(1)
    try:
        approved = json.load(open(os.path.join(ROOT, 'spec', 'release_baseline.json'), encoding='utf-8'))['font_sha256']
        if not (isinstance(approved, str) and re.fullmatch(r'[0-9a-f]{64}', approved)):
            approved = None   # malformed digest: treated as unreadable approval metadata
    except Exception:
        approved = None
    fd, tmp = tempfile.mkstemp(prefix='.' + os.path.basename(out) + '.', suffix='.ttf', dir=os.path.dirname(out)); os.close(fd)
    try:
        build(tmp)
        try: validate_sfnt(tmp)
        except FontInvalid as e: print(f'FAIL: built font is invalid ({e}); {out} left unchanged'); sys.exit(1)
        new = sha(tmp)
        if os.path.isfile(out) and approved is None and not a.replace_approved:
            print(f'FAIL: {out} exists and no valid approved SHA-256 can be read from spec/release_baseline.json; '
                  f'left unchanged (use --replace-approved to override)'); sys.exit(1)
        if os.path.isfile(out) and approved and sha(out) == approved and new != approved and not a.replace_approved:
            print(f'FAIL: {out} holds the approved release ({approved[:16]}…) and the new build differs ({new[:16]}…); '
                  f'left unchanged (use --replace-approved to override)'); sys.exit(1)
        os.chmod(tmp, 0o644); os.replace(tmp, out)
        if os.environ.get('RASMEE_TEMP_BUILD') == '1':
            print('built temporary file', new, '(approved digest)' if new == approved else '(digest differs)', '- verified next')
        else:
            print('installed', out, new, '(approved release)' if new == approved else '')
    finally:
        if os.path.exists(tmp): os.remove(tmp)
        if os.path.exists(tmp + '.tmp'): os.remove(tmp + '.tmp')


if __name__ == '__main__':
    main()
