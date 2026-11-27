"""Release overlap gate: every ordered pair of adjacent Thaana clusters, shaped with HarfBuzz.

A cluster is one base (U+0780..U+07A5 and Naa U+07B1), either alone or with one fili (U+07A6..U+07B0):
39 x 12 = 468 clusters, so 468^2 = 219,024 adjacent states. The candidate and the reference are measured
on exactly the same states.

Contact in a state is the area of the union of two intersections:
  - the fili ink of the first cluster with all ink of the second;
  - the fili ink of the second cluster with all ink of the first.
Ink shared by both directions (fili against fili) is therefore counted once. Areas are exact: they are
computed on the TrueType quadratic outlines with skia-pathops, not on flattened polygons.

Published thresholds:
  CONTACT = 1.0 unit^2  a state "has contact" when its contact area exceeds this.
  TOL     = 0.5 unit    the effective depth sqrt(area) may exceed the reference's by at most this.
A state FAILS when the candidate has contact and either:
  - the reference has no contact, or
  - sqrt(new_area) > sqrt(ref_area) + TOL.
States that are deeper than the reference but within TOL are listed separately and never include failures.

Preflight: both fonts must be valid SFNTs that map every base and fili. Each fili must shape to a
non-.notdef glyph with ink, and each base to a non-.notdef glyph with ink. Faruma's blank Naa is
allowed for the reference only.

usage: clearance_full.py font.ttf [--ref Faruma.ttf] [--json out.json] [--jobs N]
Exit status: 0 only when the preflight passes, every expected state is measured and there are no
failures; 1 otherwise."""
import sys, os, json, hashlib

for _s in (sys.stdout, sys.stderr):   # diagnostics never fail on a non-UTF-8 console: unencodable text is escaped
    try: _s.reconfigure(errors='backslashreplace')
    except Exception: pass
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONTACT, TOL = 1.0, 0.5
FARUMA_SHA256 = 'ff5985587f10897623704d8269b83e9f63e49dd58625078cac81204ee4d797e5'
BASES = [chr(c) for c in range(0x780, 0x7A6)] + ['ޱ']
FILI = [chr(c) for c in range(0x7A6, 0x7B1)]
CLUSTERS = [b + f for b in BASES for f in [''] + FILI]
EXPECTED_STATES = len(CLUSTERS) ** 2                                     # 219,024
EXPECTED_MEASURED = EXPECTED_STATES - len(BASES) ** 2                    # states with at least one fili
_M = {}


class GateError(Exception):
    pass


def _loader(path, allow_blank_bases=()):
    """Measure contacts in one font. Marks are identified by HarfBuzz cluster (cluster level 1: one cluster per
    input character), not by glyph name. Every fili in a state must shape to a non-.notdef glyph with ink, and every
    base to a non-.notdef glyph (with ink, unless listed in allow_blank_bases); otherwise GateError is raised."""
    import uharfbuzz as hb, pathops, math
    from fontTools.ttLib import TTFont
    tt = TTFont(path); order = tt.getGlyphOrder(); gs = tt.getGlyphSet(); cache = {}
    font = hb.Font(hb.Face(hb.Blob.from_file_path(path)))

    def path_of(n):
        if n not in cache:
            p = pathops.Path(); gs[n].draw(p.getPen(glyphSet=gs))
            if p.verbs:
                p.simplify()   # resolve the fill rule; degenerate/collinear outlines vanish (same test as baseline_check)
            cache[n] = p if p.verbs and abs(p.area) > 0 else None   # zero filled area counts as no ink
        return cache[n]

    def union(paths):
        paths = [p for p in paths if p is not None]
        if not paths: return None
        u = paths[0]
        for q in paths[1:]: u = pathops.op(u, q, pathops.PathOp.UNION)
        return u

    def overlap(a, b):
        if a is None or b is None: return None
        ab, bb = a.bounds, b.bounds
        if ab[2] < bb[0] or bb[2] < ab[0] or ab[3] < bb[1] or bb[3] < ab[1]: return None
        r = pathops.op(a, b, pathops.PathOp.INTERSECTION)
        return r if r.verbs else None

    def contact(c1, c2):
        text = c1 + c2
        buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties(); buf.cluster_level = 1
        hb.shape(font, buf, {})
        x = 0; ink = {1: [], 2: []}; marks = {1: [], 2: []}; seen = {}
        for i, p in zip(buf.glyph_infos, buf.glyph_positions):
            if i.codepoint == 0:
                raise GateError(f'{path}: .notdef in {text!r} (cluster {i.cluster})')
            n = order[i.codepoint]; g = path_of(n); k = 1 if i.cluster < len(c1) else 2
            ch = text[i.cluster]
            seen[i.cluster] = seen.get(i.cluster, False) or g is not None
            if g is not None:
                gg = g.transform(1, 0, 0, 1, x + p.x_offset, p.y_offset)
                ink[k].append(gg)
                if ch in FILI: marks[k].append(gg)
            x += p.x_advance
        for idx, ch in enumerate(text):
            if idx not in seen:
                raise GateError(f'{path}: character U+{ord(ch):04X} in {text!r} produced no glyph cluster')
            if not seen[idx] and not (ch in allow_blank_bases):
                raise GateError(f'{path}: U+{ord(ch):04X} in {text!r} has no ink')
        parts = [overlap(union(marks[1]), union(ink[2])), overlap(union(marks[2]), union(ink[1]))]
        u = union([q for q in parts if q is not None])
        a = abs(u.area) if u is not None else 0.0
        if not math.isfinite(a):
            raise GateError(f'{path}: non-finite contact area in {text!r}')
        return a
    return contact


def preflight(path, allow_blank_bases=()):
    """Structural checks before measuring: a valid SFNT with glyphs, and every base and fili mapped."""
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from font_checks import validate_sfnt, FontInvalid
    try:
        tt = validate_sfnt(path); cmap = tt.getBestCmap() or {}
    except FontInvalid as e:
        raise GateError(f'sfnt: {path}: {e}')
    missing = [f'U+{ord(c):04X}' for c in BASES + FILI if ord(c) not in cmap and c not in allow_blank_bases]
    if missing:
        raise GateError(f'{path}: unmapped characters {missing}')
    m = _loader(path, allow_blank_bases)
    for b in BASES:              # every base alone and with every fili must shape with inked marks
        for f in [''] + FILI:
            m(b + f, '')


REF_BLANK = ('\u07B1',)   # Faruma draws Naa as a blank base (documented); allowed for the reference only


def _work(args):
    path_new, path_ref, i = args
    if 'N' not in _M: _M['N'] = _loader(path_new); _M['R'] = _loader(path_ref, REF_BLANK)
    c1 = CLUSTERS[i]; out = []
    for c2 in CLUSTERS:
        if not any(ch in FILI for ch in c1 + c2):
            continue  # neither cluster has a fili: no mark contact is possible
        out.append((c1, c2, _M['N'](c1, c2), _M['R'](c1, c2)))
    return out


def fail(msg):
    print('FAIL:', msg); sys.exit(1)


def main():
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from font_checks import strict_parser
    ap = strict_parser('clearance_full.py'); ap.add_argument('font')
    ap.add_argument('--ref', default=os.path.join(ROOT, 'reference', 'Faruma.ttf'))
    ap.add_argument('--json'); ap.add_argument('--jobs', type=int, default=os.cpu_count())
    a = ap.parse_args(); NEW, REF = a.font, a.ref
    for p in (NEW, REF):
        if not os.path.isfile(p): fail(f'missing input {p}')
    if hashlib.sha256(open(REF, 'rb').read()).hexdigest() != FARUMA_SHA256:
        print(f'WARNING: reference SHA-256 differs from the audited Faruma ({FARUMA_SHA256})')
    jobs = a.jobs
    try:
        preflight(NEW); preflight(REF, REF_BLANK)
    except GateError as e:
        fail(f'preflight: {e}')
    except Exception as e:
        fail(f'preflight: could not read fonts ({e!r})')
    try:
        with Pool(jobs) as pool:
            rows = [r for chunk in pool.imap_unordered(_work, [(NEW, REF, i) for i in range(len(CLUSTERS))]) for r in chunk]
    except Exception as e:
        fail(f'measurement error: {e!r}')
    if len(rows) != EXPECTED_MEASURED:
        fail(f'measured {len(rows)} states, expected {EXPECTED_MEASURED}')
    n_new = sum(1 for r in rows if r[2] > CONTACT); n_ref = sum(1 for r in rows if r[3] > CONTACT)
    fails = [r for r in rows if r[2] > CONTACT and (r[3] <= CONTACT or r[2] ** 0.5 > r[3] ** 0.5 + TOL)]
    failset = {(r[0], r[1]) for r in fails}
    ties = [r for r in rows if (r[0], r[1]) not in failset and r[2] > CONTACT and r[2] ** 0.5 > r[3] ** 0.5]
    print(f'{EXPECTED_STATES} adjacent states ({len(rows)} with at least one fili); exact contact > {CONTACT} u^2: '
          f'candidate {n_new}, reference {n_ref}')
    print(f'gate failures (candidate-only contact, or depth > reference + {TOL} u): {len(fails)}')
    print(f'states deeper than reference within tolerance: {len(ties)}' +
          (f'; max excess {max(r[2] ** 0.5 - r[3] ** 0.5 for r in ties):.3f} u' if ties else ''))
    for r in sorted(fails, key=lambda r: -r[2])[:40]:
        print('  FAIL', r[0], r[1], f'new {r[2]:.2f} u2  ref {r[3]:.2f} u2')
    if a.json:
        json.dump({'thresholds': {'contact_area_u2': CONTACT, 'depth_tolerance_u': TOL}, 'states': EXPECTED_STATES,
                   'measured': len(rows), 'contact_new': n_new, 'contact_ref': n_ref,
                   'fails': fails, 'within_tolerance': ties}, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False)
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:   # never a traceback: any unexpected failure is a clean FAIL
        print(f'FAIL internal: {e!r}'); sys.exit(1)
