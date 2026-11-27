"""Spacing parity: shape a corpus with HarfBuzz in both fonts and compare every glyph id, advance and offset.

usage: shapecheck.py font.ttf [--ref Faruma.ttf] [--corpus spec/corpus.txt]   (unknown options are rejected)
Both inputs pass tools/font_checks.validate_sfnt (required tables, head invariants, bounded loca) before shaping.
Exit status: 0 only when every non-empty corpus line shapes identically in both fonts with no .notdef;
1 on any difference, .notdef, an invalid/missing input, an empty corpus or empty shaping output."""
import sys, os, hashlib

for _s in (sys.stdout, sys.stderr):   # diagnostics never fail on a non-UTF-8 console: unencodable text is escaped
    try: _s.reconfigure(errors='backslashreplace')
    except Exception: pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FARUMA_SHA256 = 'ff5985587f10897623704d8269b83e9f63e49dd58625078cac81204ee4d797e5'


def fail(msg):
    print('FAIL:', msg); sys.exit(1)


def main():
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from font_checks import strict_parser
    ap = strict_parser('shapecheck.py'); ap.add_argument('font')
    ap.add_argument('--ref', default=os.path.join(ROOT, 'reference', 'Faruma.ttf'))
    ap.add_argument('--corpus', default=os.path.join(ROOT, 'spec', 'corpus.txt'))
    a = ap.parse_args(); NEW, REF, CORPUS = a.font, a.ref, a.corpus
    for p in (NEW, REF, CORPUS):
        if not os.path.isfile(p): fail(f'missing input {p}')
    if hashlib.sha256(open(REF, 'rb').read()).hexdigest() != FARUMA_SHA256:
        print(f'WARNING: reference SHA-256 differs from the audited Faruma ({FARUMA_SHA256})')
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from font_checks import validate_sfnt, FontInvalid
    for p in (NEW, REF):   # structural TrueType validation before shaping (HarfBuzz accepts arbitrary bytes)
        try: validate_sfnt(p)
        except FontInvalid as e: fail(f'sfnt: {p}: {e}')
    import uharfbuzz as hb
    fonts = {}
    for k, p in (('ref', REF), ('new', NEW)):
        try: fonts[k] = hb.Font(hb.Face(hb.Blob.from_file_path(p)))
        except Exception as e: fail(f'cannot load {p}: {e}')

    def shape(font, text):
        buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties(); hb.shape(font, buf, {})
        return [(i.codepoint, p.x_advance, p.y_advance, p.x_offset, p.y_offset) for i, p in zip(buf.glyph_infos, buf.glyph_positions)]

    lines = [l for l in open(CORPUS, encoding='utf-8').read().split('\n') if l.strip()]
    if not lines: fail('empty corpus')
    bad = 0
    for line in lines:
        a, b = shape(fonts['ref'], line), shape(fonts['new'], line)
        if not a or not b: fail(f'shaping produced no glyphs for: {line[:40]}')
        for k, r in (('ref', a), ('new', b)):
            if any(g[0] == 0 for g in r): fail(f'.notdef in {k} shaping of: {line[:40]}')
        if a != b:
            bad += 1; print('DIFF:', line[:40]); print('  ref', a[:12]); print('  new', b[:12])
    print(f'{len(lines) - bad}/{len(lines)} lines identical in glyph sequence, advances and offsets')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:   # never a traceback: any unexpected failure is a clean FAIL
        print(f'FAIL internal: {e!r}'); sys.exit(1)
