"""Shared font validation for the release checks.

validate_sfnt(path) raises FontInvalid with a diagnostic unless the file is a structurally sound TrueType font:
- it parses as SFNT, every table lies within the file, every table checksum and the whole-file checksum
  (head.checkSumAdjustment) are correct;
- required tables are not truncated (head 54, hhea 36, maxp 32, OS/2 78, post 32 bytes minimum);
- the name table's record count, string-storage offset, every record's string extent and (version 1) every
  language-tag string extent and language-tag reference are consistent;
- the required tables (cmap, head, hhea, hmtx, maxp, name, OS/2, post, glyf, loca) are present;
- head.magicNumber == 0x5F0F3CF5, unitsPerEm is in 16..16384 and indexToLocFormat is 0 or 1;
- loca has exactly numGlyphs + 1 monotonic offsets bounded by the glyf table length;
- hmtx covers every glyph, and every glyph decompiles;
- there is at least one glyph beyond .notdef and a Unicode cmap.
Reference: https://learn.microsoft.com/en-us/typography/opentype/spec/otff and .../spec/head

exact_area(glyphset, name) returns the filled area of a glyph after applying its fill rule (skia-pathops, exact on
the quadratic outline), so collinear, degenerate or self-cancelling contours count as zero ink."""
import struct, os

REQUIRED = ('cmap', 'head', 'hhea', 'hmtx', 'maxp', 'name', 'OS/2', 'post', 'glyf', 'loca')
HEAD_MAGIC = 0x5F0F3CF5


class FontInvalid(Exception):
    pass


MIN_LEN = {'head': 54, 'hhea': 36, 'maxp': 32, 'OS/2': 78, 'post': 32, 'cmap': 4, 'name': 6}


def _file_checksum_ok(path):
    """head.checkSumAdjustment must make the whole-file uint32 sum equal 0xB1B0AFBA."""
    data = open(path, 'rb').read()
    data += b'\0' * (-len(data) % 4)
    return sum(struct.unpack('>%dI' % (len(data) // 4), data)) & 0xFFFFFFFF == 0xB1B0AFBA


def _check_name(raw):
    """name table: record count, string-storage offset and every record's string extent must be consistent."""
    fmt, count, soff = struct.unpack('>HHH', raw[:6])
    if fmt not in (0, 1):
        raise FontInvalid(f'name table format {fmt} invalid')
    rec_end = 6 + 12 * count; ltc = 0; tags = []
    if fmt == 1:
        if len(raw) < rec_end + 2: raise FontInvalid('name table truncated (records)')
        ltc, = struct.unpack('>H', raw[rec_end:rec_end + 2])
        if len(raw) < rec_end + 2 + 4 * ltc: raise FontInvalid('name table truncated (language-tag records)')
        tags = [struct.unpack('>HH', raw[rec_end + 2 + 4 * j:rec_end + 6 + 4 * j]) for j in range(ltc)]
        rec_end += 2 + 4 * ltc
    if count == 0:
        raise FontInvalid('name table has no records')
    if len(raw) < rec_end or soff < rec_end or soff > len(raw):
        raise FontInvalid(f'name table truncated or inconsistent (count {count}, stringOffset {soff}, length {len(raw)})')
    for j, (ln, off) in enumerate(tags):
        if soff + off + ln > len(raw):
            raise FontInvalid(f'name language-tag record {j} string extends beyond the name table '
                              f'(ends at {soff + off + ln}, table length {len(raw)})')
    for i in range(count):
        pid, eid, lid, nid, ln, off = struct.unpack('>HHHHHH', raw[6 + 12 * i:18 + 12 * i])
        if soff + off + ln > len(raw):
            raise FontInvalid(f'name record {i} (nameID {nid}) string extends beyond the name table')
        if lid >= 0x8000 and pid != 1 and lid - 0x8000 >= ltc:
            raise FontInvalid(f'name record {i} (nameID {nid}) references missing language tag {lid - 0x8000}')


def validate_sfnt(path):
    try:
        return _validate(path)
    except FontInvalid:
        raise
    except AssertionError as e:
        raise FontInvalid(f'table checksum mismatch ({e})')
    except Exception as e:
        raise FontInvalid(f'unreadable font structure ({e!r})')


def _validate(path):
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.sfnt import SFNTReader
    try:
        with open(path, 'rb') as f:
            rd = SFNTReader(f, checkChecksums=0)
            dir_ = {t: rd.tables[t] for t in rd.keys()}
            for t, e in dir_.items():
                if e.offset + e.length > os.path.getsize(path):
                    raise FontInvalid(f'table {t} truncated (extends beyond the end of the file)')
            # explicit table checksums (no reliance on assert, so this also holds under python -O / PYTHONOPTIMIZE)
            from fontTools.ttLib.sfnt import calcChecksum
            for t, e in dir_.items():
                data = rd[t]
                if t == 'head' and len(data) >= 12:
                    data = data[:8] + b'\0\0\0\0' + data[12:]
                if calcChecksum(data) != e.checkSum:
                    raise FontInvalid(f'table checksum mismatch for {t!r}')
        tt = TTFont(path, lazy=False, checkChecksums=0)
    except FontInvalid:
        raise
    except AssertionError as e:
        raise FontInvalid(f'table checksum mismatch ({e})')
    except Exception as e:
        raise FontInvalid(f'not a valid SFNT font ({e!r})')
    missing = [t for t in REQUIRED if t not in tt.reader]
    if missing:
        raise FontInvalid(f'missing required table(s) {missing}')
    for t, n in MIN_LEN.items():
        if len(tt.reader[t]) < n:
            raise FontInvalid(f'table {t} truncated ({len(tt.reader[t])} bytes, minimum {n})')
    if not _file_checksum_ok(path):
        raise FontInvalid('file checksum mismatch (head.checkSumAdjustment)')
    _check_name(tt.reader['name'])
    raw_head = tt.reader['head']
    magic, = struct.unpack('>I', raw_head[12:16]); upm, = struct.unpack('>H', raw_head[18:20])
    loc_fmt, = struct.unpack('>h', raw_head[50:52])
    if magic != HEAD_MAGIC:
        raise FontInvalid(f'head.magicNumber is 0x{magic:08X}, expected 0x{HEAD_MAGIC:08X}')
    if not 16 <= upm <= 16384:
        raise FontInvalid(f'head.unitsPerEm {upm} out of range')
    if loc_fmt not in (0, 1):
        raise FontInvalid(f'head.indexToLocFormat {loc_fmt} invalid')
    n = struct.unpack('>H', tt.reader['maxp'][4:6])[0]
    raw_loca, glyf_len = tt.reader['loca'], len(tt.reader['glyf'])
    fmt, size = ('>%dH' % (n + 1), 2) if loc_fmt == 0 else ('>%dI' % (n + 1), 4)
    if len(raw_loca) != (n + 1) * size:
        raise FontInvalid(f'loca length {len(raw_loca)} bytes, expected exactly {(n + 1) * size} (numGlyphs+1 offsets)')
    nhm = struct.unpack('>H', tt.reader['hhea'][34:36])[0]
    if nhm < 1 or nhm > n or len(tt.reader['hmtx']) < 4 * nhm + 2 * (n - nhm):
        raise FontInvalid('hmtx truncated or numberOfHMetrics invalid')
    offs = [o * (2 if loc_fmt == 0 else 1) for o in struct.unpack(fmt, raw_loca[:(n + 1) * size])]
    if any(b < a for a, b in zip(offs, offs[1:])) or offs[-1] > glyf_len:
        raise FontInvalid('loca offsets not monotonic or beyond the glyf table')
    try:
        order = tt.getGlyphOrder(); glyf = tt['glyf']; hmtx = tt['hmtx']
        for g in order:
            glyf[g]; hmtx[g]
    except Exception as e:
        raise FontInvalid(f'glyph data does not decompile ({e!r})')
    if n < 2 or len(order) != n:
        raise FontInvalid('font has no glyphs beyond .notdef, or glyph count mismatch')
    if not tt.getBestCmap():
        raise FontInvalid('no Unicode cmap')
    return tt


def exact_area(glyphset, name):
    import pathops
    p = pathops.Path(); glyphset[name].draw(p.getPen(glyphSet=glyphset))
    if not p.verbs:
        return 0.0
    p.simplify()   # resolve the fill rule: overlaps unioned, degenerate and collinear contours removed
    return abs(p.area)


class _Parser(__import__('argparse').ArgumentParser):
    """argparse with exit status 1 and a one-line FAIL usage diagnostic (no defaults chosen on a typo)."""
    def error(self, message):
        print(f'FAIL usage: {message}. ' + self.format_usage().strip()); raise SystemExit(1)


def strict_parser(prog, description=''):
    return _Parser(prog=prog, description=description, allow_abbrev=False, add_help=True)


def validate_added_coverage(manifest_path, baseline):
    """The release-owned added-coverage manifest must be exactly the one recorded with the approved baseline and be
    internally consistent with it. Returns the list of code points; raises FontInvalid with a diagnostic."""
    import json, hashlib as _h
    try:
        raw = open(manifest_path, 'rb').read(); m = json.loads(raw)
    except FileNotFoundError:
        raise FontInvalid(f'added-coverage manifest not found: {manifest_path}')
    except Exception as e:
        raise FontInvalid(f'added-coverage manifest unreadable ({e!r})')
    want = baseline.get('added_coverage_sha256')
    if not want:
        raise FontInvalid('baseline records no added_coverage_sha256')
    got = _h.sha256(raw).hexdigest()
    if got != want:
        raise FontInvalid(f'added-coverage manifest SHA-256 {got} differs from the approved {want} (edited or incomplete)')
    if m.get('approved_font_sha256') != baseline.get('font_sha256'):
        raise FontInvalid('added-coverage manifest was recorded for a different font')
    cps, cmap, glyphs = [], baseline['cmap'], baseline['glyphs']
    for row in m.get('code_points', []):
        cp = int(row['cp'][2:], 16)
        if cp in cps: raise FontInvalid(f"added-coverage manifest lists {row['cp']} twice")
        if cmap.get(str(cp)) != row['glyph']:
            raise FontInvalid(f"added-coverage manifest row {row['cp']} -> {row['glyph']} disagrees with the approved cmap")
        area = glyphs[row['glyph']]['area']
        kind = 'control' if 0x200C <= cp <= 0x200F else ('inked' if area > 0 else 'blank')
        if row['kind'] != kind:
            raise FontInvalid(f"added-coverage manifest row {row['cp']} kind {row['kind']} should be {kind}")
        cps.append(cp)
    if not cps:
        raise FontInvalid('added-coverage manifest is empty')
    return cps
