"""Signed ink clearance for every Thaana base x fili pair, shaped with HarfBuzz (uharfbuzz).
Reports the minimum distance between base ink and mark ink (negative = overlap) in both the
reference and the candidate.
usage: clearance.py font.ttf [--ref Faruma.ttf] [--json out]   (strict options; both fonts validated)
Bases and fili are identified by HarfBuzz cluster (one cluster per character), not by glyph name; any .notdef fails.
Exit status 1 if the candidate has an own-letter fili overlap where the reference is clear, if any candidate fili or
base is missing or blank (Faruma's blank Naa is allowed for the reference only), or on any invalid input."""
import sys, os, json

for _s in (sys.stdout, sys.stderr):   # diagnostics never fail on a non-UTF-8 console: unencodable text is escaped
    try: _s.reconfigure(errors='backslashreplace')
    except Exception: pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely import affinity
from raster import contours

BASES = [chr(c) for c in range(0x780, 0x7A6)] + ['ޱ']
FILI = [chr(c) for c in range(0x7A6, 0x7B1)]


def loader(path):
    tt = TTFont(path); order = tt.getGlyphOrder(); cache = {}
    face = hb.Face(hb.Blob.from_file_path(path)); font = hb.Font(face)
    def geom(name):
        if name not in cache:
            g = None
            for c in contours(tt, name):
                if len(c) < 3: continue
                p = Polygon(c).buffer(0); g = p if g is None else g.symmetric_difference(p)
            cache[name] = g
        return cache[name]
    def shape(text):
        """Shape with one HarfBuzz cluster per input character; returns (role, geometry) with role 'mark' for glyphs
        of a fili character and 'base' otherwise. Raises Missing on .notdef."""
        buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties(); buf.cluster_level = 1
        hb.shape(font, buf, {})
        out = []; x = 0
        for i, p in zip(buf.glyph_infos, buf.glyph_positions):
            if i.codepoint == 0:
                raise Missing(f'.notdef for U+{ord(text[i.cluster]):04X} in {text!r}')
            g = geom(order[i.codepoint]); role = 'mark' if text[i.cluster] in FILI else 'base'
            out.append((role, affinity.translate(g, x + p.x_offset, p.y_offset) if g is not None else None))
            x += p.x_advance
        return out
    return shape


class Missing(Exception):
    pass


def clearance(shape, b, f, allow_blank_base=False):
    """Signed clearance between a base and its fili; raises Missing if the fili (or, unless allowed, the base) has
    no glyph or no filled ink after shaping."""
    gl = shape(b + f)
    marks = [g for r, g in gl if r == 'mark' and g is not None]
    bases = [g for r, g in gl if r == 'base' and g is not None]
    mark = unary_union(marks) if marks else None
    base = unary_union(bases) if bases else None
    if mark is None or mark.is_empty or mark.area <= 0:
        raise Missing(f'U+{ord(f):04X} on U+{ord(b):04X}: fili has no glyph or no ink')
    if base is None or base.is_empty or base.area <= 0:
        if allow_blank_base: return None
        raise Missing(f'U+{ord(b):04X}: base has no glyph or no ink')
    if base.intersects(mark): return -round(base.intersection(mark).area ** 0.5)
    return round(base.distance(mark))


def main():
    from font_checks import strict_parser, validate_sfnt, FontInvalid
    ap = strict_parser('clearance.py'); ap.add_argument('font')
    ap.add_argument('--ref', default=os.path.join(ROOT, 'reference', 'Faruma.ttf')); ap.add_argument('--json')
    a = ap.parse_args(); NEW, REF = a.font, a.ref
    for label, p in (('font', NEW), ('reference', REF)):
        if not os.path.isfile(p): print(f'FAIL: {label} not found: {p}'); sys.exit(1)
        try: validate_sfnt(p)
        except FontInvalid as e: print(f'FAIL: sfnt: {p}: {e}'); sys.exit(1)
    sr, sn = loader(REF), loader(NEW)
    rows = []; worst = []
    for b in BASES:
        for f in FILI:
            try:
                n = clearance(sn, b, f)
            except Missing as e:
                print(f'FAIL: candidate {e}'); sys.exit(1)
            try:
                r = clearance(sr, b, f, allow_blank_base=(b == '\u07B1'))   # Faruma's documented blank Naa
            except Missing as e:
                print(f'FAIL: reference {e}'); sys.exit(1)
            rows.append((f'U+{ord(b):04X}', f'U+{ord(f):04X}', r, n))
            if n is not None and (n < 25 or (r is not None and n < r - 40)): worst.append(rows[-1])
    new_only = [x for x in rows if x[3] is not None and x[3] < 0 and (x[2] is None or x[2] >= 0)]
    measured = sum(1 for x in rows if x[3] is not None)
    print(f'{len(rows)} pairs checked ({measured} measured in the candidate, {sum(1 for x in rows if x[2] is not None)} in the reference); candidate overlaps: {sum(1 for x in rows if x[3] is not None and x[3] < 0)}; reference overlaps: {sum(1 for x in rows if x[2] is not None and x[2] < 0)}')
    print('tight/regressed pairs (base, fili, ref, new):')
    for w in sorted(worst, key=lambda x: x[3]): print('  ', w)
    if a.json: json.dump(rows, open(a.json, 'w', encoding='utf-8'))
    if new_only:
        print(f'FAIL: {len(new_only)} own-letter fili overlap(s) where the reference is clear: {new_only[:5]}'); sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f'FAIL internal: {e!r}'); sys.exit(1)
