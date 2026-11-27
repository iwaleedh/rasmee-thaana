"""One-command release QA with designated, self-verified negative controls.

1. Preflight
   - Candidate and reference must exist and pass tools/font_checks.validate_sfnt.
   - A reference whose SHA-256 is not the audited Faruma is reported as a WARNING in the summary.
2. Candidate: shapecheck, script_tests, baseline_check and clearance_full must each exit 0. If any fails, QA stops
   here with a FAIL summary; controls are not run.
3. Controls: each broken copy is generated, then reopened to verify that the intended change, and only that change,
   is present and the compared properties are otherwise unchanged:
   - glyph records, whole Unicode cmap dictionaries, kern pairs, hhea ascent/descent/lineGap and head timestamps
     for fontTools-saved controls;
   - every other table byte for byte, for raw-table controls.
   fontTools saving also regenerates loca and recalculates maxp, head.flags, the head bbox and the derived hhea
   fields; these are not compared, and the approved digest in baseline_check still rejects them. Then:
   - the DESIGNATED check must exit with status exactly 1;
   - every EXPECTED diagnostic (a regex anchored at the start of a line) must appear in its output;
   - the output must contain no Python traceback.
   A crash, a signal, another exit status or an unrelated message does not count. The other checks are also run
   and logged for information (clearance_full only where designated). Reference controls are passed as --ref
   with the real candidate.

  control            designated      expected (line-anchored)
  shifted            clearance_full  gate failures ...: N>0               uni07AEnsp component 400 down
  lifted             baseline_check  REJECT fili-pos: '.ޮ'                uni07AEnsp component 2,200 up
  unmapped           baseline_check  REJECT cmap: U+07A6 ... U+07B0       11 fili removed from every subtable
  erased             baseline_check  REJECT ink: uni07AEnsp               outline emptied
  zero-area          baseline_check  REJECT ink: uni07AEnsp               closed collinear outline
  blank-symbols      baseline_check  REJECT ink: uni25CC/grave/uniFDF2/uniFDFD
  latin-removed      baseline_check  REJECT cmap: U+00E9, U+20AC          added code points below U+2100 unmapped
  metrics            baseline_check  REJECT metrics: hhea, REJECT digest  hhea ascent +100
  kerning            baseline_check  REJECT kern: 1 kern pair(s)          one pair +60
  cmap-one-subtable  baseline_check  REJECT cmap-subtable: (3,1,4) ... U+0780, and the disagreement line
                                                                          U+0780 removed from (3,1) only
  cmap-unicode-remap baseline_check  REJECT cmap-subtable: (0,3,4), and disagreement
                                                                          U+00E9 remapped in (0,3) only
  ink-in-space       baseline_check  REJECT blank: space
  mirrored-fdfd      baseline_check  REJECT outline: uniFDFD, REJECT alias
  combined           baseline_check  all of metrics/kern/cmap-subtable/blank/outline/alias/digest
  no-outlines        shapecheck      FAIL: sfnt: ... missing required table(s)
  bad-head           shapecheck      FAIL: sfnt: ... head.magicNumber
  garbage            shapecheck      FAIL: sfnt: ... not a valid SFNT
  truncated-table    shapecheck      FAIL: sfnt: ... table hhea truncated
  loca-count         shapecheck      FAIL: sfnt: ... loca length
  checksum           shapecheck      FAIL: sfnt: ... checksum mismatch
  ref-name-header    shapecheck      FAIL: sfnt: <ref> ... name table      reference name records stripped (as --ref)
  erased-gate        clearance_full  FAIL: preflight: ... U+07AE ... has no ink   the erased fixture, through the gate
  zero-area-gate     clearance_full  FAIL: preflight: ... U+07AE ... has no ink   the zero-area fixture, through the gate
  ref-name-v1-langtag shapecheck     FAIL: sfnt: ... language-tag record 0 ...  version-1 name, tag string out of bounds (as --ref)
usage: release_qa.py font.ttf [--ref Faruma.ttf] [--out DIR]     exit 0 only if every expectation holds.
Each run writes its logs and SUMMARY.txt into a NEW directory (DIR/run-<timestamp>-<random>/, or a temporary
directory), so a failed or interrupted run can never leave earlier pass logs looking current. SUMMARY.txt is written
for EVERY outcome (preflight, candidate, control generation, controls, internal) and records the candidate and
reference paths, the stage, the result and the diagnostic; the run directory is printed on stdout. An interrupted run
(Ctrl-C) writes stage 'cancelled', result FAIL, and exits with status 130."""
import sys, os, re, subprocess, tempfile, shutil, hashlib, struct

for _s in (sys.stdout, sys.stderr):   # diagnostics never fail on a non-UTF-8 console: unencodable text is escaped
    try: _s.reconfigure(errors='backslashreplace')
    except Exception: pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
PY = sys.executable
T = lambda n: os.path.join(ROOT, 'tools', n)
FARUMA_SHA256 = 'ff5985587f10897623704d8269b83e9f63e49dd58625078cac81204ee4d797e5'
FILI_CPS = range(0x7A6, 0x7B1)

# name -> (designated check, [line-anchored regexes], passes the control as the reference instead of the candidate)
CONTROLS = {
    'shifted': ('clearance_full', [r'^gate failures \(candidate-only contact, or depth > reference \+ 0\.5 u\): [1-9]\d*$'], False),
    'lifted': ('baseline_check', [r"^REJECT fili-pos: '.ޮ' fili ink "], False),
    'unmapped': ('baseline_check', [rf'^REJECT cmap: U\+{c:04X} baseline \S+ candidate None$' for c in FILI_CPS], False),
    'erased': ('baseline_check', [r'^REJECT ink: uni07AEnsp has no filled area'], False),
    'zero-area': ('baseline_check', [r'^REJECT ink: uni07AEnsp has no filled area'], False),
    'blank-symbols': ('baseline_check', [rf'^REJECT ink: {n} has no filled area' for n in ('uni25CC', 'grave', 'uniFDF2', 'uniFDFD')], False),
    'latin-removed': ('baseline_check', [r'^REJECT cmap: U\+00E9 baseline eacute candidate None$', r'^REJECT cmap: U\+20AC baseline Euro candidate None$'], False),
    'metrics': ('baseline_check', [r'^REJECT metrics: hhea ', r'^REJECT digest: file SHA-256 '], False),
    'kerning': ('baseline_check', [r'^REJECT kern: 1 kern pair\(s\) differ'], False),
    'cmap-one-subtable': ('baseline_check', [r"^REJECT cmap-subtable: Unicode subtable \(3,1,4\) differs: missing \['U\+0780'\]",
                                             r'^REJECT cmap-subtable: Unicode subtables disagree on '], False),
    'cmap-unicode-remap': ('baseline_check', [r'^REJECT cmap-subtable: Unicode subtable \(0,3,4\) differs',
                                              r'^REJECT cmap-subtable: Unicode subtables disagree on '], False),
    'ink-in-space': ('baseline_check', [r'^REJECT blank: space must stay blank'], False),
    'mirrored-fdfd': ('baseline_check', [r'^REJECT outline: uniFDFD outline differs', r'^REJECT alias: U\+FDFD'], False),
    'combined': ('baseline_check', [r'^REJECT digest: ', r'^REJECT metrics: hhea ', r'^REJECT kern: 1 kern pair\(s\) differ',
                                    r"^REJECT cmap-subtable: Unicode subtable \(3,1,4\) differs: missing \['U\+0780'\]",
                                    r'^REJECT cmap-subtable: Unicode subtables disagree on ', r'^REJECT blank: space must stay blank',
                                    r'^REJECT outline: uniFDFD outline differs', r'^REJECT alias: U\+FDFD'], False),
    'no-outlines': ('shapecheck', [r"^FAIL: sfnt: .*missing required table\(s\) \['glyf', 'loca'\]"], False),
    'bad-head': ('shapecheck', [r'^FAIL: sfnt: .*head\.magicNumber is 0x00000000'], False),
    'garbage': ('shapecheck', [r'^FAIL: sfnt: .*not a valid SFNT font'], False),
    'truncated-table': ('shapecheck', [r'^FAIL: sfnt: .*table hhea truncated'], False),
    'loca-count': ('shapecheck', [r'^FAIL: sfnt: .*loca length \d+ bytes, expected exactly'], False),
    'checksum': ('shapecheck', [r"^FAIL: sfnt: .*checksum mismatch for 'name'"], False),
    'ref-name-header': ('shapecheck', [r'^FAIL: sfnt: .*ref-name-header\.ttf: name table'], True),
    'erased-gate': ('clearance_full', [r"^FAIL: preflight: .*erased-gate\.ttf: U\+07AE in '.\u07AE' has no ink"], False),
    'zero-area-gate': ('clearance_full', [r"^FAIL: preflight: .*zero-area-gate\.ttf: U\+07AE in '.\u07AE' has no ink"], False),
    'ref-name-v1-langtag': ('shapecheck', [r'^FAIL: sfnt: .*ref-name-v1-langtag\.ttf: name language-tag record 0 string extends beyond'], True),
}


def run(cmd, log):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3600, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        out, rc = r.stdout + r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        out, rc = 'TIMEOUT', -999
    open(log, 'w', encoding='utf-8').write(out + f'\nexit={rc}\n')
    return rc, out


def _raw_copy(src, dst, drop=(), patch=None):
    """Write an SFNT from raw table data (table checksums recomputed), so damaged fonts need no recompiling."""
    from fontTools.ttLib.sfnt import SFNTReader, SFNTWriter
    with open(src, 'rb') as f:
        rd = SFNTReader(f); data = {t: rd[t] for t in rd.keys() if t not in drop}
    if patch: data = patch(data)
    with open(dst, 'wb') as f:
        w = SFNTWriter(f, len(data), rd.sfntVersion)
        for t in sorted(data): w[t] = data[t]
        w.close()


def _unicode_subtables(path):
    from fontTools.ttLib import TTFont
    return {(t.platformID, t.platEncID): dict(t.cmap) for t in TTFont(path)['cmap'].tables if t.isUnicode()}


ADDED = os.path.join(ROOT, 'spec', 'added_coverage.json')


def _glyph_bytes(tt):
    g = tt['glyf']
    return {n: g[n].compile(g) for n in tt.getGlyphOrder()}


def _tables(path):
    """Raw table data; head.checkSumAdjustment (bytes 8-11) is zeroed because writing any file recomputes it."""
    from fontTools.ttLib.sfnt import SFNTReader
    with open(path, 'rb') as f:
        rd = SFNTReader(f); t = {k: rd[k] for k in rd.keys()}
    if 'head' in t and len(t['head']) >= 12: t['head'] = t['head'][:8] + b'\0\0\0\0' + t['head'][12:]
    return t


def name_v1(raw, bad):
    """Re-encode a name table as version 1 with one language-tag record (the 'en' tag appended to storage).
    bad=True points the tag beyond the table (offset 0xFFFF-len, a valid 16-bit value), as a corrupt but checksummed
    reference would. Requires the result to stay within 16-bit fields, which the caller verifies."""
    fmt, count, soff = struct.unpack('>HHH', raw[:6])
    recs = raw[6:6 + 12 * count]; storage = raw[soff:]
    tag = 'en'.encode('utf-16-be')
    off = (0xFFFF - len(tag)) if bad else len(storage)   # bad: largest 16-bit offset, beyond any real storage
    new_soff = 6 + 12 * count + 2 + 4
    if new_soff > 0xFFFF or (not bad and off > 0xFFFF) or (bad and new_soff + len(storage) + len(tag) >= new_soff + off + len(tag)):
        raise AssertionError('ref-name-v1-langtag: reference name table too large for a 16-bit out-of-bounds tag offset')
    return struct.pack('>HHH', 1, count, new_soff) + recs + struct.pack('>HHH', 1, len(tag), off) + storage + tag


def make_controls(font, ref, d):
    """Build every control, then verify it against its source: the intended change is present and nothing else
    changed (glyph records, cmap dictionaries, kern pairs or raw tables, per control). Returns ({name: path},
    {name: extra expected diagnostics}); raises AssertionError naming the control on any mismatch."""
    import json
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables._g_l_y_f import Glyph
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib.sfnt import SFNTReader
    P = lambda n: os.path.join(d, n + '.ttf'); out = {}; extra = {}
    load = lambda p: TTFont(p, recalcTimestamp=False)
    orig = load(font); og = _glyph_bytes(orig); osub = _unicode_subtables(font); otab = _tables(font)
    okern = dict(orig['kern'].kernTables[0].kernTable)
    added = [int(e['cp'][2:], 16) for e in json.load(open(ADDED, encoding='utf-8'))['code_points']]
    added_low = [c for c in added if c < 0x2100]

    def save(name, mutate):
        f = load(font); mutate(f); f.save(P(name)); out[name] = P(name)

    def empty(f, n):
        g = Glyph(); g.numberOfContours = 0; f['glyf'][n] = g

    def comp_y(f, dy):
        f['glyf']['uni07AEnsp'].components[0].y += dy
    save('shifted', lambda f: comp_y(f, -400))
    save('lifted', lambda f: comp_y(f, 2200))

    def unmap(f):
        for t in f['cmap'].tables:
            t.cmap = {k: v for k, v in t.cmap.items() if k not in FILI_CPS}
    save('unmapped', unmap)
    save('erased', lambda f: empty(f, 'uni07AEnsp'))

    def zero(f):
        pen = TTGlyphPen(None); pen.moveTo((100, 1100)); pen.lineTo((300, 1100)); pen.lineTo((500, 1100)); pen.lineTo((200, 1100)); pen.closePath()
        f['glyf']['uni07AEnsp'] = pen.glyph()
    save('zero-area', zero)
    save('blank-symbols', lambda f: [empty(f, n) for n in ('uni25CC', 'grave', 'uniFDF2', 'uniFDFD')])

    def latin(f):   # release-owned set (spec/added_coverage.json), independent of --ref
        for t in f['cmap'].tables: t.cmap = {k: v for k, v in t.cmap.items() if k not in added_low}
    save('latin-removed', latin)
    kpair = sorted(okern)[0]

    def metrics(f): f['hhea'].ascent += 100
    def kerning(f): f['kern'].kernTables[0].kernTable[kpair] += 60
    def cmap_one(f):   # replace the (possibly shared) mapping, so only (3,1) changes
        for t in f['cmap'].tables:
            if (t.platformID, t.platEncID) == (3, 1): t.cmap = {k: v for k, v in t.cmap.items() if k != 0x0780}
    def cmap_uni(f):
        for t in f['cmap'].tables:
            if (t.platformID, t.platEncID) == (0, 3): t.cmap = dict(t.cmap); t.cmap[0x00E9] = 'e'
    def ink_space(f):
        pen = TTGlyphPen(None); pen.moveTo((100, 0)); pen.lineTo((100, 300)); pen.lineTo((300, 300)); pen.lineTo((300, 0)); pen.closePath()
        f['glyf']['space'] = pen.glyph()
    def mirror_fdfd(f):
        g = f['glyf']['uniFDFD']
        if not g.isComposite():
            raise AssertionError('mirrored-fdfd: uniFDFD is not a composite in this candidate')
        c = g.components[0]; c.transform = [[-1, 0], [0, 1]]; c.x += f['hmtx']['uniFDFD'][0]
    for name, fns in (('metrics', [metrics]), ('kerning', [kerning]), ('cmap-one-subtable', [cmap_one]),
                      ('cmap-unicode-remap', [cmap_uni]), ('ink-in-space', [ink_space]), ('mirrored-fdfd', [mirror_fdfd]),
                      ('combined', [metrics, kerning, cmap_one, ink_space, mirror_fdfd])):
        save(name, lambda f, fns=fns: [fn(f) for fn in fns])
    _raw_copy(font, P('no-outlines'), drop=('glyf', 'loca')); out['no-outlines'] = P('no-outlines')

    def badhead(data):
        h = bytearray(data['head']); h[12:16] = b'\0\0\0\0'; data['head'] = bytes(h); return data
    _raw_copy(font, P('bad-head'), patch=badhead); out['bad-head'] = P('bad-head')
    open(P('garbage'), 'wb').write(b'not a font ' * 400); out['garbage'] = P('garbage')
    _raw_copy(font, P('truncated-table'), patch=lambda data: {**data, 'hhea': data['hhea'][:20]}); out['truncated-table'] = P('truncated-table')
    _raw_copy(font, P('loca-count'), patch=lambda data: {**data, 'loca': data['loca'] + b'\0\0\0\0'}); out['loca-count'] = P('loca-count')
    shutil.copy(font, P('checksum'))   # flip one byte inside the name table without fixing its checksum
    with open(font, 'rb') as fh: e = SFNTReader(fh).tables['name']
    flip_at = e.offset + e.length - 1
    with open(P('checksum'), 'r+b') as fh:
        fh.seek(flip_at); b = fh.read(1); fh.seek(flip_at); fh.write(bytes([b[0] ^ 0x20]))
    out['checksum'] = P('checksum')
    _raw_copy(ref, P('ref-name-header'), patch=lambda data: {**data, 'name': data['name'][:6]}); out['ref-name-header'] = P('ref-name-header')

    shutil.copy(out['erased'], P('erased-gate')); out['erased-gate'] = P('erased-gate')
    shutil.copy(out['zero-area'], P('zero-area-gate')); out['zero-area-gate'] = P('zero-area-gate')
    _raw_copy(ref, P('ref-name-v1-langtag'), patch=lambda data: {**data, 'name': name_v1(data['name'], bad=True)})
    out['ref-name-v1-langtag'] = P('ref-name-v1-langtag')

    # ---- verification: intended change present, nothing else changed
    def changed_glyphs(name):
        g = _glyph_bytes(load(out[name])); return {n for n in og if g.get(n) != og[n]}
    def check(cond, name, what):
        if not cond: raise AssertionError(f'control {name}: {what}')
    glyph_ctrls = {'shifted': {'uni07AEnsp'}, 'lifted': {'uni07AEnsp'}, 'erased': {'uni07AEnsp'}, 'zero-area': {'uni07AEnsp'},
                   'blank-symbols': {'uni25CC', 'grave', 'uniFDF2', 'uniFDFD'}, 'ink-in-space': {'space'},
                   'mirrored-fdfd': {'uniFDFD'}, 'combined': {'space', 'uniFDFD'},
                   'erased-gate': {'uni07AEnsp'}, 'zero-area-gate': {'uni07AEnsp'}}
    for name in out:
        if name in ('garbage', 'no-outlines', 'bad-head', 'truncated-table', 'loca-count', 'checksum', 'ref-name-header', 'ref-name-v1-langtag'): continue
        check(changed_glyphs(name) == glyph_ctrls.get(name, set()), name, f'changed glyphs {sorted(changed_glyphs(name))}')
        c = load(out[name])
        check(c['head'].modified == orig['head'].modified and c['head'].created == orig['head'].created, name, 'head timestamps changed')
    for name, dy in (('shifted', -400), ('lifted', 2200)):
        check(load(out[name])['glyf']['uniFDFD'] is not None and
              load(out[name])['glyf']['uni07AEnsp'].components[0].y - orig['glyf']['uni07AEnsp'].components[0].y == dy, name, 'component offset')
    for name, want in (('unmapped', {k: {c: g for c, g in m.items() if c not in FILI_CPS} for k, m in osub.items()}),
                       ('latin-removed', {k: {c: g for c, g in m.items() if c not in added_low} for k, m in osub.items()}),
                       ('cmap-one-subtable', {**osub, (3, 1): {c: g for c, g in osub[(3, 1)].items() if c != 0x0780}}),
                       ('cmap-unicode-remap', {**osub, (0, 3): {**osub[(0, 3)], 0x00E9: 'e'}}),
                       ('combined', {**osub, (3, 1): {c: g for c, g in osub[(3, 1)].items() if c != 0x0780}})):
        check(_unicode_subtables(out[name]) == want, name, 'Unicode cmap subtables are not exactly the intended dictionaries')
    for name in out:
        if name in ('unmapped', 'latin-removed', 'cmap-one-subtable', 'cmap-unicode-remap', 'combined', 'garbage',
                    'no-outlines', 'bad-head', 'truncated-table', 'loca-count', 'checksum', 'ref-name-header', 'ref-name-v1-langtag'): continue
        check(_unicode_subtables(out[name]) == osub, name, 'cmap changed')
    for name in out:
        if name in ('garbage', 'no-outlines', 'bad-head', 'truncated-table', 'loca-count', 'checksum', 'ref-name-header', 'ref-name-v1-langtag'): continue
        k = dict(load(out[name])['kern'].kernTables[0].kernTable)
        want = {**okern, kpair: okern[kpair] + 60} if name in ('kerning', 'combined') else okern
        check(k == want, name, 'kern pairs not as intended')
        hh, oh = load(out[name])['hhea'], orig['hhea']
        check(hh.ascent - oh.ascent == (100 if name in ('metrics', 'combined') else 0) and hh.descent == oh.descent and hh.lineGap == oh.lineGap,
              name, 'hhea metrics not as intended')
    for name, want in (('no-outlines', {t: v for t, v in otab.items() if t not in ('glyf', 'loca')}),
                       ('truncated-table', {**otab, 'hhea': otab['hhea'][:20]}),
                       ('loca-count', {**otab, 'loca': otab['loca'] + b'\0\0\0\0'})):
        check(_tables(out[name]) == want, name, 'raw tables not exactly as intended')
    bh = _tables(out['bad-head'])
    check(bh['head'][12:16] == b'\0' * 4 and bh['head'][:12] == otab['head'][:12] and bh['head'][16:] == otab['head'][16:]
          and {t: v for t, v in bh.items() if t != 'head'} == {t: v for t, v in otab.items() if t != 'head'}, 'bad-head', 'not exactly magicNumber zeroed')
    a_, b_ = open(font, 'rb').read(), open(out['checksum'], 'rb').read()
    diff = [i for i in range(len(a_)) if a_[i] != b_[i]]
    check(len(a_) == len(b_) and diff == [flip_at], 'checksum', f'bytes changed at {diff[:5]}')
    rt, ct = _tables(ref), _tables(out['ref-name-header'])
    check(ct['name'] == rt['name'][:6] and {t: v for t, v in ct.items() if t != 'name'} == {t: v for t, v in rt.items() if t != 'name'},
          'ref-name-header', 'reference tables not exactly as intended')
    nv = _tables(out['ref-name-v1-langtag'])['name']
    check(struct.unpack('>H', nv[:2])[0] == 1 and {t: v for t, v in _tables(out['ref-name-v1-langtag']).items() if t != 'name'}
          == {t: v for t, v in rt.items() if t != 'name'}, 'ref-name-v1-langtag', 'not a version-1 name table on an otherwise identical reference')
    for name in ('erased-gate', 'zero-area-gate'):
        check(open(out[name], 'rb').read() == open(out[name.replace('-gate', '')], 'rb').read(), name, 'differs from its source control')
    extra['kerning'] = [rf"^REJECT kern: 1 kern pair\(s\) differ, e\.g\. \[\({kpair[0]!r}, {kpair[1]!r}\)\]"]
    extra['combined'] = extra['kerning']
    return out, extra


_RUN = {}


def finish(ok, stage, diagnostic, lines=()):
    """Single terminal writer: SUMMARY.txt (candidate, reference, stage, result, diagnostic, warnings, run directory)
    in the run directory for every outcome, printed as well; then exit 0 (pass) or 1."""
    result = 'PASS' if ok else 'FAIL'
    head = [f"candidate: {_RUN.get('font')}", f"reference: {_RUN.get('ref')}", f'stage: {stage}', f'result: {result}',
            f'diagnostic: {diagnostic}'] + [f'WARNING: {w}' for w in _RUN.get('warnings', [])] + [f"run directory: {_RUN.get('outdir')}"]
    if _RUN.get('outdir'):
        with open(os.path.join(_RUN['outdir'], 'SUMMARY.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(head + list(lines)) + '\n')
    for w in _RUN.get('warnings', []): print('WARNING:', w)
    print(f'RELEASE QA {result} [{stage}]: {diagnostic} (run directory {_RUN.get("outdir")})')
    sys.exit(0 if ok else 1)


def main():
    from font_checks import strict_parser
    ap = strict_parser('release_qa.py'); ap.add_argument('font')
    ap.add_argument('--ref', default=os.path.join(ROOT, 'reference', 'Faruma.ttf')); ap.add_argument('--out')
    a = ap.parse_args(); font, ref = a.font, a.ref
    _RUN.update(font=os.path.abspath(font), ref=os.path.abspath(ref), warnings=[])
    # every run writes to its own fresh directory, so an early failure can never leave earlier pass logs in place
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        import time
        outdir = tempfile.mkdtemp(prefix=time.strftime('run-%Y%m%d-%H%M%S-'), dir=a.out)
    else:
        outdir = tempfile.mkdtemp(prefix='release_qa-')
    _RUN['outdir'] = outdir
    from font_checks import validate_sfnt, FontInvalid
    warnings = _RUN['warnings']
    for label, p in (('candidate', font), ('reference', ref)):
        if not os.path.isfile(p):
            finish(False, 'preflight', f'{label} not found: {p}')
        try: validate_sfnt(p)
        except FontInvalid as e:
            finish(False, 'preflight', f'{label} rejected: {e}')
    import json as _json
    try:
        from font_checks import validate_added_coverage
        validate_added_coverage(ADDED, _json.load(open(os.path.join(ROOT, 'spec', 'release_baseline.json'), encoding='utf-8')))
    except FontInvalid as e:
        finish(False, 'preflight', f'release-owned coverage list: {e}')
    except Exception as e:
        finish(False, 'preflight', f'release baseline unreadable ({e!r})')
    if hashlib.sha256(open(ref, 'rb').read()).hexdigest() != FARUMA_SHA256:
        warnings.append(f'reference is NOT the audited Faruma (SHA-256 {FARUMA_SHA256}); comparisons are against {ref}')
    checks = {'shapecheck': [PY, T('shapecheck.py'), '{f}', '--ref', '{r}'],
              'script_tests': [PY, T('script_tests.py'), '{f}', '--ref', '{r}'],
              'baseline_check': [PY, T('baseline_check.py'), '{f}'],
              'clearance_full': [PY, T('clearance_full.py'), '{f}', '--ref', '{r}']}
    fill = lambda cmd, f, r: [c.replace('{f}', f).replace('{r}', r) for c in cmd]
    ok = True; lines = []
    print('candidate:', font); print('reference:', ref); print('run directory:', outdir)
    for name, cmd in checks.items():
        rc, out = run(fill(cmd, font, ref), os.path.join(outdir, f'candidate_{name}.txt'))
        tail = [l for l in out.strip().splitlines() if not l.startswith('added coverage')][-3:]
        line = f'  {name:15s} exit {rc}  ' + ' | '.join(tail); print(line); lines.append(line); ok &= rc == 0
    if not ok:
        bad = [n for n in checks if f'  {n:15s} exit 0' not in '\n'.join(lines)]
        finish(False, 'candidate', f'candidate rejected by {bad}; controls not run', lines)
    tmp = tempfile.mkdtemp()
    try:
        try:
            paths, extra = make_controls(font, ref, tmp)
        except Exception as e:
            finish(False, 'control generation', f'control generation or verification failed: {e!r}', lines)
        for cname, (designated, patterns, as_ref) in CONTROLS.items():
            rcs = {}; dout = ''
            for name, cmd in checks.items():
                if name == 'clearance_full' and designated != 'clearance_full': continue
                if as_ref and name == 'baseline_check': continue
                f, r = (font, paths[cname]) if as_ref else (paths[cname], ref)
                rcs[name], out = run(fill(cmd, f, r), os.path.join(outdir, f'control_{cname}_{name}.txt'))
                if name == designated: dout = out
            missing = [p for p in patterns + extra.get(cname, []) if not re.search(p, dout, re.M)]
            hit = rcs[designated] == 1 and 'Traceback' not in dout and not missing
            line = (f'  control {cname:18s} ' + ' '.join(f'{k}={v}' for k, v in rcs.items()) +
                    f'  designated {designated}: ' + ('REJECTED as expected' if hit else
                    f'NOT REJECTED AS EXPECTED (exit {rcs[designated]}, missing {missing})'))
            print(line); lines.append(line); ok &= hit
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    finish(ok, 'controls', f'{len(CONTROLS)} controls ' + ('all rejected as designated' if ok else 'NOT all rejected as designated'), lines)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except KeyboardInterrupt:   # Ctrl-C: record the cancellation in the run's SUMMARY.txt, never a stale pass
        if _RUN.get('outdir'):
            try: finish(False, 'cancelled', 'interrupted by the user (Ctrl-C); the run is incomplete')
            except SystemExit: sys.exit(130)
        print('RELEASE QA FAIL [cancelled]: interrupted by the user (Ctrl-C)'); sys.exit(130)
    except Exception as e:
        if _RUN.get('outdir'):
            try: finish(False, 'internal', f'internal error {e!r}')
            except SystemExit: raise
        print(f'RELEASE QA FAIL [internal]: internal error {e!r}'); sys.exit(1)
