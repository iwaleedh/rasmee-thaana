"""Calligraphic stroke engine.

A glyph is drawn as a set of pen strokes along skeleton paths. The pen is an
ellipse (width W along angle A, height H) swept along the path; an optional
width profile scales the nib along the stroke (tapering). Strokes are unioned
into clean outlines with shapely, then oriented for TrueType (clockwise outer).

Path syntax (font units, y up), SVG-like and absolute only:
    "M x y  C x1 y1 x2 y2 x y  Q x1 y1 x y  L x y"
"""
import math, re
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, Point
from shapely.ops import unary_union
from shapely.geometry.polygon import orient

# Default nib, tuned to the reference colour (stroke ~150-160u at 2048 UPM)
NIB = dict(w=195, h=142, angle=30, sq=3.0)


def _parse(path):
    toks = re.findall(r'[MCQL]|-?\d+(?:\.\d+)?', path)
    segs, cur, i = [], None, 0
    while i < len(toks):
        c = toks[i]; i += 1
        n = {'M': 2, 'L': 2, 'Q': 4, 'C': 6}[c]
        # allow repeated coordinate groups after a command
        while True:
            vals = [float(v) for v in toks[i:i + n]]; i += n
            pts = [(vals[k], vals[k + 1]) for k in range(0, n, 2)]
            if c == 'M':
                cur = pts[0]
            else:
                segs.append((c, [cur] + pts)); cur = pts[-1]
            if i < len(toks) and toks[i] not in 'MCQL':
                if c == 'M': c, n = 'L', 2
                continue
            break
    return segs


def _bez(pts, t):
    p = np.array(pts, float)
    while len(p) > 1:
        p = (1 - t) * p[:-1] + t * p[1:]
    return p[0]


def sample(path, step=5.0):
    """Return Nx2 array of points along the path, roughly `step` apart."""
    out = []
    for c, pts in _parse(path):
        # estimate length
        fine = np.array([_bez(pts, t) for t in np.linspace(0, 1, 40)])
        L = np.sum(np.linalg.norm(np.diff(fine, axis=0), axis=1))
        n = max(2, int(L / step))
        ts = np.linspace(0, 1, n + 1)
        seg = [_bez(pts, t) for t in ts]
        if out:
            seg = seg[1:]
        out.extend(seg)
    return np.array(out)


def _ellipse(cx, cy, w, h, ang, n=40, sq=2.0):
    """Superellipse nib (sq=2: ellipse; sq>2: squarer, blunt flat-cut terminals)."""
    a = math.radians(ang)
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    c, s_ = np.cos(t), np.sin(t)
    x = (w / 2) * np.sign(c) * np.abs(c) ** (2 / sq); y = (h / 2) * np.sign(s_) * np.abs(s_) ** (2 / sq)
    xr = x * math.cos(a) - y * math.sin(a); yr = x * math.sin(a) + y * math.cos(a)
    return np.column_stack([xr + cx, yr + cy])


def _profile(prof, s):
    """prof: list of (t, k) knots, t in [0,1]; piecewise smoothstep interpolation."""
    if prof is None:
        return np.ones_like(s)
    ts = [p[0] for p in prof]; ks = [p[1] for p in prof]
    out = np.empty_like(s)
    for i, v in enumerate(s):
        j = np.searchsorted(ts, v) - 1
        j = min(max(j, 0), len(ts) - 2)
        u = (v - ts[j]) / max(1e-9, ts[j + 1] - ts[j]); u = min(max(u, 0), 1)
        u = u * u * (3 - 2 * u)
        out[i] = ks[j] + (ks[j + 1] - ks[j]) * u
    return out


# Skeleton transform (sx, sy, cx, cy): scales skeleton points about (cx, cy) before the pen
# is swept, so glyph size can be fitted to target metrics without changing stroke weight.
SKEL_T = None
# Pen scale multiplier (per-glyph colour matching)
PEN_K = 1.0


def _facet(geom, P, T, back, fa):
    """Cut a flat nib facet: remove the half-plane beyond a line through P - T*back at angle fa."""
    from shapely.geometry import Polygon as _P
    a = math.radians(fa); D = np.array([math.cos(a), math.sin(a)])
    Q = P - T * back
    N = np.array([-D[1], D[0]])
    if np.dot(N, -T) < 0: N = -N            # N points outward (away from the stroke body)
    big = 4000
    poly = _P([Q - D * big, Q + D * big, Q + D * big + N * big, Q - D * big + N * big])
    return geom.difference(poly)


def stroke(path, w=None, h=None, angle=None, profile=None, step=5.0, sq=None, facet0=None, facet1=None):
    """Sweep an elliptical nib along `path`. Returns a shapely geometry.
    facet0/facet1 = (angle_deg, back_units): flat oblique nib cut at the start/end terminal."""
    w = w or NIB['w']; h = h or NIB['h']; angle = NIB['angle'] if angle is None else angle
    sq = sq or NIB['sq']
    pts = sample(path, step)
    if SKEL_T is not None:
        sx, sy, cx, cy = SKEL_T
        pts = np.column_stack([cx + (pts[:, 0] - cx) * sx, cy + (pts[:, 1] - cy) * sy])
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    s = d / d[-1] if d[-1] > 0 else d
    k = _profile(profile, s)
    ells = [_ellipse(p[0], p[1], w * kk * PEN_K, h * kk * PEN_K, angle, n=48, sq=sq) for p, kk in zip(pts, k)]
    hulls = []
    for a, b in zip(ells[:-1], ells[1:]):
        hulls.append(Polygon(np.vstack([a, b])).convex_hull)
    if not hulls:
        hulls = [Polygon(ells[0])]
    g = unary_union(hulls)
    if facet0 and len(pts) > 3:
        T = pts[3] - pts[0]; T = T / (np.linalg.norm(T) or 1)
        g = _facet(g, pts[0], T, facet0[1] * PEN_K, facet0[0])
    if facet1 and len(pts) > 3:
        T = pts[-4] - pts[-1]; T = T / (np.linalg.norm(T) or 1)
        g = _facet(g, pts[-1], T, facet1[1] * PEN_K, facet1[0])
    if facet0 or facet1:
        g = g.buffer(-38, join_style=1).buffer(38, join_style=1)  # soften the facet corners
    if facet0 and ENTRY_ROUND and len(pts) > 3 and CURRENT not in ENTRY_ROUND_SKIP:
        # Noofaru-style entry: round the faceted entry terminal into a soft blob. A morphological
        # opening (radius ENTRY_ROUND) is applied only inside a window around the stroke start,
        # so the rest of the stroke keeps its exact outline.
        r, win = ENTRY_ROUND
        P0 = pts[0]; Tn = pts[min(len(pts) - 1, 12)] - P0; Tn = Tn / (np.linalg.norm(Tn) or 1)
        disk = Point(*(P0 + Tn * win * 0.25)).buffer(win, 64)
        opened = g.buffer(-r, join_style=1).buffer(r, join_style=1)
        g = unary_union([g.difference(disk), opened.intersection(disk)]).buffer(0)
    return g


# Optional entry-terminal rounding (radius, window) — None keeps the approved Rasmee Thaana outlines.
_er = __import__('os').environ.get('RASMEE_ENTRY_ROUND')
ENTRY_ROUND = tuple(float(v) for v in _er.split(',')) if _er else None
# Noofaru rounds letters only; the fili keep their faceted entry.
ENTRY_ROUND_SKIP = {'uni%04X' % u for u in range(0x07A6, 0x07B1)}
CURRENT = None   # glyph being drawn (set by src/thaana.py)


def dot(cx, cy, w=200, h=190, angle=20, sq=2.35):
    return Polygon(_ellipse(cx, cy, w * PEN_K, h * PEN_K, angle, n=64, sq=sq))


def ring(path, **kw):
    """Closed loop stroke (path should end where it starts)."""
    return stroke(path, **kw)


def finalize(geoms, simplify=0.6):
    """Union, clean and orient. Returns list of contours (lists of (x,y)), TrueType orientation."""
    g = unary_union([x for x in geoms if x is not None and not x.is_empty]).buffer(0)
    if simplify:
        g = g.simplify(simplify, preserve_topology=True)
    polys = [g] if isinstance(g, Polygon) else list(getattr(g, 'geoms', []))
    contours = []
    for p in polys:
        if p.area < 50:
            continue
        p = orient(p, sign=-1.0)  # exterior clockwise, holes counter-clockwise
        contours.append(_despike(list(p.exterior.coords)[:-1]))
        for r in p.interiors:
            contours.append(_despike(list(r.coords)[:-1]))
    return contours


def _despike(c, eps=1.0):
    """Remove zero-width spikes (A -> B -> A' with A' within eps of A) and duplicate vertices, cyclically."""
    c = [tuple(v) for v in c]
    changed = True
    while changed and len(c) > 3:
        changed = False
        n = len(c)
        for i in range(n):
            a, b, d = c[i - 1], c[i], c[(i + 1) % n]
            if math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6 or math.hypot(a[0] - d[0], a[1] - d[1]) < eps:
                # drop the spike tip b (and the returning duplicate d if it coincides with a)
                drop = {i} if math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6 else {i, (i + 1) % n}
                c = [v for k, v in enumerate(c) if k not in drop]
                changed = True
                break
    return c
