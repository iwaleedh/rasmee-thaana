"""Approved-baseline gate: the candidate must match the reviewed release in coverage, ink and mark placement.

The baseline (spec/release_baseline.json) is recorded from the approved font with --write. It holds:
  - the exact Unicode cmap (code point -> glyph name), including the added Latin coverage;
  - for every glyph: advance, exact filled area (fill rule applied; tools/font_checks.exact_area) and ink bounds;
  - for every base and the dotted circle, each with every fili, shaped as Thaana with HarfBuzz:
    - the positioned ink bounds of the fili;
    - the exact contact area between the fili and its own letter or carrier.
Checks (each failure prints 'REJECT <code>: ...'):
  sfnt      structural TrueType validation (tools/font_checks.validate_sfnt)
  digest    the file SHA-256 differs from the approved release; 'table' lines name each changed table
  metrics   unitsPerEm, hhea/typo/win line metrics, fsSelection or xAvgCharWidth differ
  name      any name record differs
  kern      any legacy kern pair differs;  layout: GPOS, GSUB or GDEF differs
  cmap-subtable  a Unicode cmap subtable differs from the baseline, or two subtables disagree
  blank     a glyph that is blank in the approved release has ink
  outline   a glyph's decomposed outline differs (catches mirrored or moved outlines of equal area)
  alias     the U+FDFD and backtick Bismillah outlines are not identical
  manifest  spec/added_coverage.json is not exactly the manifest recorded with the approved baseline (SHA-256), or a
            row disagrees with the approved cmap or ink
  cmap      any missing, extra or remapped code point
  advance   any glyph advance differs
  ink       a glyph with ink in the baseline has no filled area
  area      filled area differs by more than AREA_TOL (relative)
  bounds    glyph ink bounds differ by more than POS_TOL units
  fili-pos  a positioned fili's ink bounds differ by more than POS_TOL units
  own-contact  fili/own-letter contact exceeds the baseline by more than CONTACT_TOL u^2
usage: baseline_check.py font.ttf [--baseline spec/release_baseline.json]
       baseline_check.py APPROVED.ttf --write --ref Faruma.ttf   (record a new baseline after review approval;
                         refused unless --ref is the audited Faruma and spec/added_coverage.json is exactly the
                         approved font's additions over it)
Exit status 0 only when nothing is rejected."""
import sys, os, json, hashlib

for _s in (sys.stdout, sys.stderr):   # diagnostics never fail on a non-UTF-8 console: unencodable text is escaped
    try: _s.reconfigure(errors='backslashreplace')
    except Exception: pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
from font_checks import validate_sfnt, exact_area, FontInvalid

AREA_TOL, POS_TOL, CONTACT_TOL = 0.01, 4.0, 1.0
BASES = [chr(c) for c in range(0x780, 0x7A6)] + ['ޱ', '◌']
FILI = [chr(c) for c in range(0x7A6, 0x7B1)]
DEFAULT = os.path.join(ROOT, 'spec', 'release_baseline.json')
FARUMA_SHA256 = 'ff5985587f10897623704d8269b83e9f63e49dd58625078cac81204ee4d797e5'
ADDED = os.path.join(ROOT, 'spec', 'added_coverage.json')


def measure(path):
    import uharfbuzz as hb, pathops
    tt = validate_sfnt(path); gs = tt.getGlyphSet(); order = tt.getGlyphOrder()
    glyphs = {}
    for n in order:
        p = pathops.Path(); gs[n].draw(p.getPen(glyphSet=gs))
        a = exact_area(gs, n)
        glyphs[n] = {'adv': tt['hmtx'][n][0], 'area': round(a, 2),
                     'bounds': [round(v, 1) for v in p.bounds] if a > 0 else None}
    font = hb.Font(hb.Face(hb.Blob.from_file_path(path)))
    paths = {}
    def path_of(n):
        if n not in paths:
            p = pathops.Path(); gs[n].draw(p.getPen(glyphSet=gs)); p.simplify(); paths[n] = p if p.verbs else None
        return paths[n]
    def union(ps):
        ps = [q for q in ps if q is not None]
        if not ps: return None
        u = ps[0]
        for q in ps[1:]: u = pathops.op(u, q, pathops.PathOp.UNION)
        return u
    marks = {}
    for b in BASES:
        for f in FILI:
            t = b + f
            buf = hb.Buffer(); buf.add_str(t); buf.script = 'Thaa'; buf.direction = 'rtl'; buf.language = 'dv'
            buf.cluster_level = 1; hb.shape(font, buf, {})
            x = 0; base_ink, mark_ink = [], []
            for i, p in zip(buf.glyph_infos, buf.glyph_positions):
                g = path_of(order[i.codepoint])
                if g is not None:
                    gg = g.transform(1, 0, 0, 1, x + p.x_offset, p.y_offset)
                    (mark_ink if t[i.cluster] in FILI else base_ink).append(gg)
                x += p.x_advance
            m, bi = union(mark_ink), union(base_ink)
            contact = 0.0
            if m is not None and bi is not None:
                r = pathops.op(m, bi, pathops.PathOp.INTERSECTION); contact = abs(r.area) if r.verbs else 0.0
            marks[t] = {'mark_bounds': [round(v, 1) for v in m.bounds] if m is not None and abs(m.area) > 0 else None,
                        'contact': round(contact, 2)}
    cmap = {str(k): v for k, v in sorted(tt.getBestCmap().items())}
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    outlines = {}
    for n in order:
        rp = DecomposingRecordingPen(gs); gs[n].draw(rp)
        outlines[n] = hashlib.sha256(repr([(op, [None if pt is None else tuple(round(v, 3) for v in pt) for pt in args]) for op, args in rp.value]).encode()).hexdigest()[:24]
    subtables = {f'{t.platformID},{t.platEncID},{t.format}': {str(k): v for k, v in sorted(t.cmap.items())}
                 for t in tt['cmap'].tables if t.isUnicode()}
    h, hh, os2 = tt['head'], tt['hhea'], tt['OS/2']
    metrics = {'unitsPerEm': h.unitsPerEm, 'hhea': [hh.ascent, hh.descent, hh.lineGap],
               'typo': [os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap], 'win': [os2.usWinAscent, os2.usWinDescent],
               'fsSelection': os2.fsSelection, 'xAvgCharWidth': os2.xAvgCharWidth}
    names = sorted([n.platformID, n.platEncID, n.langID, n.nameID, n.toUnicode()] for n in tt['name'].names)
    kern = sorted([a, b, v] for st in (tt['kern'].kernTables if 'kern' in tt else []) for (a, b), v in st.kernTable.items())
    tables = {t: hashlib.sha256(tt.reader[t]).hexdigest()[:24] for t in tt.reader.keys()}
    return {'cmap': cmap, 'cmap_subtables': subtables, 'glyphs': glyphs, 'marks': marks, 'outlines': outlines,
            'metrics': metrics, 'names': names, 'kern': kern, 'tables': tables,
            'file_sha256': hashlib.sha256(open(path, 'rb').read()).hexdigest()}


def main():
    from font_checks import strict_parser
    ap = strict_parser('baseline_check.py'); ap.add_argument('font'); ap.add_argument('--baseline', default=DEFAULT)
    ap.add_argument('--write', action='store_true', help='record a new baseline from an approved font')
    ap.add_argument('--ref', help='audited Faruma (required with --write) to verify spec/added_coverage.json')
    a = ap.parse_args(); font, bpath, write = a.font, a.baseline, a.write
    if write and not a.ref:
        print('REJECT usage: --write requires --ref <audited Faruma> so the coverage list can be verified'); sys.exit(1)
    if not os.path.isfile(font):
        print(f'REJECT input: candidate font not found: {font}'); sys.exit(1)
    try:
        cur = measure(font)
    except FontInvalid as e:
        print(f'REJECT sfnt: {e}'); sys.exit(1)
    except Exception as e:
        print(f'REJECT sfnt: could not measure font ({e!r})'); sys.exit(1)
    if write:
        # the release-owned coverage list must be exactly (approved font cmap) minus (audited Faruma cmap)
        from fontTools.ttLib import TTFont
        if not os.path.isfile(a.ref):
            print(f'REJECT input: reference not found: {a.ref}'); sys.exit(1)
        ref_sha = hashlib.sha256(open(a.ref, 'rb').read()).hexdigest()
        if ref_sha != FARUMA_SHA256:
            print(f'REJECT baseline: --ref is not the audited Faruma (SHA-256 {FARUMA_SHA256}); baseline not written'); sys.exit(1)
        try:
            validate_sfnt(a.ref); man = json.load(open(ADDED, encoding='utf-8'))
        except Exception as e:
            print(f'REJECT baseline: cannot read reference or coverage list ({e!r}); baseline not written'); sys.exit(1)
        rc = TTFont(a.ref).getBestCmap(); fc = {int(k): v for k, v in cur['cmap'].items()}
        derived = {}
        for c in sorted(c for c in fc if c not in rc):
            area = cur['glyphs'][fc[c]]['area']
            derived[f'U+{c:04X}'] = (fc[c], 'control' if 0x200C <= c <= 0x200F else ('inked' if area > 0 else 'blank'))
        rows = man.get('code_points', [])
        listed = {r['cp']: (r['glyph'], r['kind']) for r in rows}
        dups = sorted({r['cp'] for r in rows if sum(1 for q in rows if q['cp'] == r['cp']) > 1})
        if dups:
            print(f'REJECT baseline: spec/added_coverage.json lists duplicate code point(s) {dups}; baseline not written'); sys.exit(1)
        if listed != derived:
            miss = sorted(set(derived) - set(listed))[:5]; extra = sorted(set(listed) - set(derived))[:5]
            wrong = sorted(k for k in set(derived) & set(listed) if derived[k] != listed[k])[:5]
            print(f'REJECT baseline: spec/added_coverage.json is not exactly the font-vs-Faruma additions '
                  f'(missing {miss}, extra {extra}, wrong {wrong}); baseline not written'); sys.exit(1)
        if man.get('approved_font_sha256') != cur['file_sha256'] or man.get('audited_faruma_sha256') != ref_sha:
            print('REJECT baseline: spec/added_coverage.json records different font or reference digests; baseline not written'); sys.exit(1)
        cur['font_sha256'] = cur['file_sha256']
        cur['added_coverage_sha256'] = hashlib.sha256(open(ADDED, 'rb').read()).hexdigest()
        cur['tolerances'] = {'area_rel': AREA_TOL, 'position_u': POS_TOL, 'contact_u2': CONTACT_TOL}
        import tempfile
        bdir = os.path.dirname(os.path.abspath(bpath))
        fd, tmpb = tempfile.mkstemp(prefix='.release_baseline.', suffix='.json', dir=bdir)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                json.dump(cur, fh, ensure_ascii=False, indent=0, sort_keys=True)
            json.load(open(tmpb, encoding='utf-8'))   # the written baseline must read back before it replaces the approved one
            mode = (os.stat(bpath).st_mode & 0o7777) if os.path.exists(bpath) else 0o644
            os.chmod(tmpb, mode); os.replace(tmpb, bpath)   # atomic: a failed write leaves the previous baseline intact
        finally:
            if os.path.exists(tmpb): os.remove(tmpb)
        print('baseline written', bpath, 'from', cur['font_sha256']); return
    try:
        base = json.load(open(bpath, encoding='utf-8'))
        for k in ('font_sha256', 'tables', 'metrics', 'names', 'kern', 'cmap', 'cmap_subtables', 'glyphs', 'outlines', 'marks'):
            base[k]
    except FileNotFoundError:
        print(f'REJECT baseline: baseline file not found: {bpath}'); sys.exit(1)
    except (ValueError, KeyError, TypeError) as e:
        print(f'REJECT baseline: baseline file unreadable or incomplete ({e!r}): {bpath}'); sys.exit(1)
    rej = []
    from font_checks import validate_added_coverage
    try:
        validate_added_coverage(ADDED, base)
    except FontInvalid as e:
        rej.append(('manifest', str(e)))
    bc, cc = base['cmap'], cur['cmap']
    for k in sorted(set(bc) | set(cc), key=int):
        if bc.get(k) != cc.get(k):
            rej.append(('cmap', f'U+{int(k):04X} baseline {bc.get(k)} candidate {cc.get(k)}'))
    for n, b in base['glyphs'].items():
        c = cur['glyphs'].get(n)
        if c is None: rej.append(('cmap', f'glyph {n} missing')); continue
        if c['adv'] != b['adv']: rej.append(('advance', f'{n} {b["adv"]} -> {c["adv"]}'))
        if b['area'] > 0:
            if c['area'] <= 0: rej.append(('ink', f'{n} has no filled area (baseline {b["area"]} u2)')); continue
            if abs(c['area'] - b['area']) > AREA_TOL * b['area']:
                rej.append(('area', f'{n} filled area {b["area"]} -> {c["area"]} u2'))
            if c['bounds'] and max(abs(x - y) for x, y in zip(c['bounds'], b['bounds'])) > POS_TOL:
                rej.append(('bounds', f'{n} ink bounds {b["bounds"]} -> {c["bounds"]}'))
    for t, b in base['marks'].items():
        c = cur['marks'].get(t)
        if b['mark_bounds'] and (not c or not c['mark_bounds']):
            rej.append(('ink', f'fili in {t!r} has no positioned ink')); continue
        if b['mark_bounds'] and max(abs(x - y) for x, y in zip(c['mark_bounds'], b['mark_bounds'])) > POS_TOL:
            rej.append(('fili-pos', f'{t!r} fili ink {b["mark_bounds"]} -> {c["mark_bounds"]}'))
        if c and c['contact'] > b['contact'] + CONTACT_TOL:
            rej.append(('own-contact', f'{t!r} fili/own-letter contact {b["contact"]} -> {c["contact"]} u2'))
    if cur['file_sha256'] != base['font_sha256']:
        rej.append(('digest', f'file SHA-256 {cur["file_sha256"]} differs from the approved {base["font_sha256"]}'))
        for t in sorted(set(base['tables']) | set(cur['tables'])):
            if base['tables'].get(t) != cur['tables'].get(t):
                rej.append(('table', f'{t} differs from the approved release'))
    if cur['metrics'] != base['metrics']:
        for k in base['metrics']:
            if cur['metrics'].get(k) != base['metrics'][k]:
                rej.append(('metrics', f'{k} {base["metrics"][k]} -> {cur["metrics"].get(k)}'))
    if cur['names'] != base['names']:
        bn, cn = {tuple(x[:4]): x[4] for x in base['names']}, {tuple(x[:4]): x[4] for x in cur['names']}
        for k in sorted(set(bn) | set(cn)):
            if bn.get(k) != cn.get(k): rej.append(('name', f'record {k} {bn.get(k)!r} -> {cn.get(k)!r}'))
    if cur['kern'] != base['kern']:
        bk, ck = {(a, b): v for a, b, v in base['kern']}, {(a, b): v for a, b, v in cur['kern']}
        diff = [k for k in set(bk) | set(ck) if bk.get(k) != ck.get(k)]
        rej.append(('kern', f'{len(diff)} kern pair(s) differ, e.g. {sorted(diff)[:3]}'))
    for t in ('GPOS', 'GSUB', 'GDEF'):
        if base['tables'].get(t) != cur['tables'].get(t):
            rej.append(('layout', f'{t} table differs from the approved release (kerning/marks/substitution)'))
    for sub in sorted(set(base['cmap_subtables']) | set(cur['cmap_subtables'])):
        b, c = base['cmap_subtables'].get(sub), cur['cmap_subtables'].get(sub)
        if b != c:
            miss = sorted(set(b or {}) - set(c or {}), key=int)[:5]; extra = sorted(set(c or {}) - set(b or {}), key=int)[:5]
            rej.append(('cmap-subtable', f'Unicode subtable ({sub}) differs: missing {[f"U+{int(k):04X}" for k in miss]} extra {[f"U+{int(k):04X}" for k in extra]}'))
    subs = list(cur['cmap_subtables'].values())
    for a in subs:
        for b in subs:
            dis = [k for k in a if k in b and a[k] != b[k]] + [k for k in a if int(k) <= 0xFFFF and k not in b]
            if dis:
                rej.append(('cmap-subtable', f'Unicode subtables disagree on {len(dis)} code point(s), e.g. U+{int(dis[0]):04X}')); break
    for n, b in base['glyphs'].items():
        c = cur['glyphs'].get(n)
        if c is not None and b['area'] == 0 and c['area'] > 0:
            rej.append(('blank', f'{n} must stay blank but has {c["area"]} u2 of ink'))
    for n, d in base['outlines'].items():
        if cur['outlines'].get(n, d) != d:
            rej.append(('outline', f'{n} outline differs from the approved release'))
    if cur['outlines'].get('grave') != cur['outlines'].get('uniFDFD'):
        rej.append(('alias', 'U+FDFD (uniFDFD) and backtick (grave) Bismillah outlines differ'))
    counts = {}
    for code, _ in rej: counts[code] = counts.get(code, 0) + 1
    for code, msg in rej: print(f"REJECT {code}: {msg}")
    print(f'baseline {base.get("font_sha256", "?")[:16]}…: {len(base["glyphs"])} glyphs, {len(base["cmap"])} code points, '
          f'{len(base["marks"])} fili placements checked; rejections: {len(rej)} {counts if counts else ""}')
    sys.exit(1 if rej else 0)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:   # never a traceback: any unexpected failure is a clean rejection
        print(f'REJECT internal: {e!r}'); sys.exit(1)
