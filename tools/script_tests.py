"""Explicit script-run assertions against Faruma (known results), complementing the corpus check.

1. Dotted-circle carrier, explicit Thaana run, all 11 fili:
   - advance 1,229 units, identical to Faruma;
   - the lower fili U+07A8 and U+07A9 are positioned exactly as in Faruma;
   - the nine upper fili sit exactly +175 units higher, the documented deliberate difference.
2. Mixed-script text: each line is split into script runs (Thaana and Arabic RTL, Latin LTR; spaces,
   digits and punctuation join the surrounding run). Every run must shape identically in both fonts:
   glyph names, advances and offsets.
3. Aliases:
   - backtick U+0060 gives the Bismillah glyph 'grave' at 5,509 units in both fonts;
   - U+FDF2 is identical in both fonts;
   - U+FDFD maps to 'uniFDFD' (5,509) here, while Faruma has no mapping (.notdef, 2,048): a documented
     coverage and width difference.
4. Added Latin coverage: representative Windows-1252 additions (é É ü ß ç ñ € £ © ° ½ œ Š … – — ‘ ’ “ ”)
   must each shape to one inked glyph. The full added set below U+2100 is listed; its exact membership is
   asserted by tools/baseline_check.py (cmap).

usage: script_tests.py font.ttf [--ref Faruma.ttf]     exit 1 on any failed assertion."""
import sys, os

for _s in (sys.stdout, sys.stderr):   # diagnostics never fail on a non-UTF-8 console: unencodable text is escaped
    try: _s.reconfigure(errors='backslashreplace')
    except Exception: pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import uharfbuzz as hb
from fontTools.ttLib import TTFont

FILI = [chr(c) for c in range(0x7A6, 0x7B1)]
LOWER = {'ި', 'ީ'}
CARRIER_SHIFT = 175
MIXED = [
    'ދިވެހިރާއްޖޭގެ ސަރުކާރު (Official Letter No. 12/34) ރަސްމީ ލިޔުން',
    'ރައީސުލްޖުމްހޫރިއްޔާގެ އޮފީސް، Male\' 20026, Republic of Maldives.',
    'ތާރީޚު: 27 ނޮވެމްބަރު 2026 — Ref: PO/2026/17 — ސޮއި',
    'ސުވާލު؟ ޖަވާބު؛ "Quoted" ޢަދަދު 1,234.50 MVR',
    'The President\'s Office ރައީސުލްޖުމްހޫރިއްޔާ ﷲ ޝުކުރިއްޔާ',
]


def runs(text):
    def cls(ch):
        o = ord(ch)
        if 0x0780 <= o <= 0x07BF: return ('Thaa', 'rtl')
        if 0x0600 <= o <= 0x06FF or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF: return ('Arab', 'rtl')
        if ch.isalpha(): return ('Latn', 'ltr')
        return None
    out = []; cur = None; buf = ''
    for ch in text:
        c = cls(ch)
        if c is None or c == cur or cur is None:
            buf += ch; cur = cur or c
        else:
            out.append((buf, cur)); buf = ch; cur = c
    if buf: out.append((buf, cur or ('Latn', 'ltr')))
    return out


def loader(path):
    f = hb.Font(hb.Face(hb.Blob.from_file_path(path))); order = TTFont(path).getGlyphOrder()
    def shape(text, script, direction):
        b = hb.Buffer(); b.add_str(text); b.script = script; b.direction = direction
        b.language = 'dv' if script == 'Thaa' else ('ar' if script == 'Arab' else 'en'); hb.shape(f, b, {})
        return [(order[i.codepoint], p.x_advance, p.x_offset, p.y_offset) for i, p in zip(b.glyph_infos, b.glyph_positions)]
    return shape


def main():
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from font_checks import strict_parser
    ap = strict_parser('script_tests.py'); ap.add_argument('font'); ap.add_argument('--ref', default=os.path.join(ROOT, 'reference', 'Faruma.ttf'))
    a = ap.parse_args(); NEW, REF = a.font, a.ref
    for p in (NEW, REF):
        if not os.path.isfile(p): print('FAIL: missing', p); sys.exit(1)
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from font_checks import validate_sfnt, exact_area, FontInvalid
    try:
        for p in (NEW, REF): validate_sfnt(p)
        N, R = loader(NEW), loader(REF)
    except FontInvalid as e:
        print(f'FAIL sfnt: {e}'); sys.exit(1)
    fails = []; checks = 0

    # 1. explicit carrier
    for f in FILI:
        t = '◌' + f; a, b = R(t, 'Thaa', 'rtl'), N(t, 'Thaa', 'rtl'); checks += 1
        am, bm = [g for g in a if g[0].endswith('nsp')], [g for g in b if g[0].endswith('nsp')]
        adv_ok = sum(g[1] for g in a) == sum(g[1] for g in b) == 1229
        names_ok = [g[0] for g in a] == [g[0] for g in b] and len(am) == len(bm) == 1
        dy = (bm[0][3] - am[0][3]) if names_ok else None
        want = 0 if f in LOWER else CARRIER_SHIFT
        if not (adv_ok and names_ok and bm[0][2] == am[0][2] and dy == want):
            fails.append(f'carrier U+{ord(f):04X}: ref {a} new {b} (want dy {want}, advance 1229)')
    # 2. mixed script runs
    for line in MIXED:
        for text, (script, d) in runs(line):
            a, b = R(text, script, d), N(text, script, d); checks += 1
            if any(g[0] == '.notdef' for g in a + b):
                fails.append(f'.notdef in {script} run {text!r}')
            elif a != b:
                fails.append(f'{script} run differs: {text!r}\n    ref {a[:8]}\n    new {b[:8]}')
    # 3. aliases (known results)
    expect = {('`', 'Latn', 'ltr'): ([('grave', 5509, 0, 0)], [('grave', 5509, 0, 0)]),
              ('ﷲ', 'Arab', 'rtl'): ([('uniFDF2', 1677, 0, 0)], [('uniFDF2', 1677, 0, 0)]),
              ('﷽', 'Arab', 'rtl'): ([('.notdef', 2048, 0, 0)], [('uniFDFD', 5509, 0, 0)])}
    for (t, s, d), (ra, na) in expect.items():
        checks += 1
        if R(t, s, d) != ra or N(t, s, d) != na:
            fails.append(f'alias U+{ord(t):04X}: ref {R(t, s, d)} new {N(t, s, d)}; expected ref {ra} new {na}')
    # 4. added Latin coverage: representative additions must shape to an inked glyph (no .notdef), LTR
    gsn = TTFont(NEW).getGlyphSet()
    for ch in 'éÉüßçñ€£©°½œŠ…–—‘’“”':
        checks += 1
        r = N(ch, 'Latn', 'ltr')
        if len(r) != 1 or r[0][0] == '.notdef' or exact_area(gsn, r[0][0]) <= 0:
            fails.append(f'added Latin U+{ord(ch):04X} {ch!r}: shaped {r} (needs an inked glyph)')
    # 5. added coverage listing (informational)
    cn, cr = TTFont(NEW).getBestCmap(), TTFont(REF).getBestCmap()
    extra = sorted(c for c in cn if c not in cr and c < 0x2100)
    print(f'{checks} script-run assertions; failures: {len(fails)}')
    for x in fails: print('  FAIL', x)
    print(f'added coverage vs reference ({len(extra)} code points below U+2100): ' + ' '.join(f'U+{c:04X}' for c in extra))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:   # never a traceback: any unexpected failure is a clean FAIL
        print(f'FAIL internal: {e!r}'); sys.exit(1)
