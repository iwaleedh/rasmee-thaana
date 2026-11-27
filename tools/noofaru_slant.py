"""Back-slant (lean left) the Thaana glyphs of Noofaru (or Rasmee Thaana) by a fixed angle.

Touched: glyphs reachable from Thaana code points (U+0780-U+07BF) — letters, fili (spacing +
non-spacing forms), dot components used solely by Thaana composites — plus the Thaana-text
punctuation: Arabic comma U+060C (sheared with the letters) and the full stop, ؛ and ؟ (sheared
about their own ink centroid, so their positions do not move). GPOS mark anchors of slanted
glyphs are sheared too (see below). Metadata: post.italicAngle = angle, hhea caret slope to
match, and with --version: head.fontRevision, nameID 5 and head.modified.
Everything else (Latin, digits, other punctuation, Arabic incl. U+FDF2) stays byte-identical.

Shear: x' = x - (y - CENTER) * tan(angle). Shearing about the letter-body centre keeps each
letter visually centred in its unchanged advance width. Composite offsets get the linear part
only (dx' = dx - dy * tan), so composites stay exactly consistent with their sheared parts.
Hinting is y-only (SVTCA[0]); a horizontal shear keeps every y coordinate and point index, so
glyph programs stay valid and are kept.

usage: noofaru_slant.py IN.ttf OUT.ttf [--angle 5] [--center 360] [--version X.Y]
"""
import argparse, math
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph


def thaana_glyphs(f):
    cmap = f.getBestCmap(); gl = f['glyf']
    todo = [g for u, g in cmap.items() if 0x0780 <= u <= 0x07BF]
    for lk in f['GSUB'].table.LookupList.Lookup:          # nsp fili come from ccmp
        for st in lk.SubTable:
            todo += [v for k, v in getattr(st, 'mapping', {}).items() if k in todo]
    seen = set()
    while todo:
        g = todo.pop()
        if g in seen: continue
        seen.add(g)
        if gl[g].isComposite(): todo += [c.glyphName for c in gl[g].components]
    # refuse to shear a glyph that a non-Thaana glyph also uses
    other = set(cmap.values()) - seen
    for n in f.getGlyphOrder():
        if n in seen or not gl[n].isComposite(): continue
        shared = {c.glyphName for c in gl[n].components} & seen
        assert not shared, f'{n} shares {shared} with Thaana'
    assert not (seen & other)
    return seen


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('out')
    ap.add_argument('--angle', type=float, default=5.0); ap.add_argument('--center', type=float, default=360)
    ap.add_argument('--version', default=None, help='e.g. 2.1: sets head.fontRevision, nameID 5, modified date')
    a = ap.parse_args()
    t = math.tan(math.radians(a.angle)); c = a.center
    f = TTFont(a.src, recalcBBoxes=False, recalcTimestamp=False)
    gl = f['glyf']; hm = f['hmtx']
    targets = thaana_glyphs(f)
    # Thaana-text punctuation: Arabic comma U+060C shears with the letters; the full stop is
    # shared with numbers, so it shears about its own vertical centre and keeps its position.
    centers = {n: c for n in targets}
    # Dhivehi ؟ and ؛ are tall, so they also shear about their own centre (position unchanged).
    for n, own in (('afii57388', False), ('period', True), ('afii57407', True), ('afii57403', True)):
        g = gl[n]; assert not g.isComposite()
        assert not any(gl[m].isComposite() and n in [k.glyphName for k in gl[m].components]
                       for m in f.getGlyphOrder()), f'{n} is used as a component'
        if own:                         # ink centroid: shearing about it keeps the centroid's x
            from fontTools.pens.statisticsPen import StatisticsPen
            sp = StatisticsPen(glyphset=f.getGlyphSet()); f.getGlyphSet()[n].draw(sp)
            centers[n] = sp.meanY
        else:
            centers[n] = c
    targets = set(targets) | set(centers)
    for n in targets:
        g = gl[n]
        if g.isComposite():
            for comp in g.components:
                comp.x = round(comp.x - comp.y * t)
        elif g.numberOfContours > 0:
            co = g.coordinates; cy = centers[n]
            for i, (x, y) in enumerate(co):
                co[i] = (round(x - (y - cy) * t), y)
    # GPOS mark anchors (Rasmee Thaana positions fili with mark-to-base): anchors of slanted glyphs
    # get the LINEAR part of the shear only (x' = x - y*tan). For a slanted mark on a slanted base the
    # centre term would cancel anyway (offset = base - mark), so attachment is exactly the shear of the
    # original; on an unslanted carrier (dotted circle U+25CC) the mark keeps its original offset and is
    # sheared about y=CENTER like every other Thaana glyph (same result as Noofaru's fixed fili).
    gpos_changed = False
    if 'GPOS' in f:
        def sh(anchor, name):
            nonlocal gpos_changed
            if anchor is None or name not in targets: return
            assert anchor.Format in (1, 2, 3), anchor.Format
            nx = round(anchor.XCoordinate - anchor.YCoordinate * t)
            if nx != anchor.XCoordinate: anchor.XCoordinate = nx; gpos_changed = True
        for lk in f['GPOS'].table.LookupList.Lookup:
            subs = [s.ExtSubTable if lk.LookupType == 9 else s for s in lk.SubTable]
            for st in subs:
                if st.LookupType == 4:
                    for g, rec in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord): sh(rec.MarkAnchor, g)
                    for g, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                        for an in rec.BaseAnchor: sh(an, g)
                elif st.LookupType in (5, 6):
                    raise SystemExit(f'GPOS lookup type {st.LookupType} not handled')
    for n in targets:                                       # bounds + lsb after all parts moved
        g = gl[n]
        if g.numberOfContours == 0: continue
        g.recalcBounds(gl)
        hm[n] = (hm[n][0], g.xMin)
    f.save(a.out)
    # restore every untouched glyph record byte-for-byte, then fix global bounds
    o = TTFont(a.out, recalcBBoxes=False, recalcTimestamp=False)
    raw = TTFont(a.src, lazy=True); rd = raw.reader['glyf']; rl = raw['loca']
    og = o['glyf']
    for i, n in enumerate(raw.getGlyphOrder()):
        if n not in targets: og.glyphs[n] = Glyph(rd[rl[i]:rl[i + 1]])
    boxes = []
    for n in o.getGlyphOrder():
        g = og[n]
        if g.numberOfContours == 0: continue
        g.recalcBounds(og); boxes.append((n, g.xMin, g.yMin, g.xMax, g.yMax))
    hd = o['head']; hh = o['hhea']; om = o['hmtx']
    hd.xMin = min(b[1] for b in boxes); hd.yMin = min(b[2] for b in boxes)
    hd.xMax = max(b[3] for b in boxes); hd.yMax = max(b[4] for b in boxes)
    hh.minLeftSideBearing = min(om[b[0]][1] for b in boxes)
    hh.minRightSideBearing = min(om[b[0]][0] - om[b[0]][1] - (b[3] - b[1]) for b in boxes)
    hh.xMaxExtent = max(om[b[0]][1] + (b[3] - b[1]) for b in boxes)
    # slant metadata: positive italicAngle = leans left (counter-clockwise); caret leans with it
    # (an upright font may store the vertical caret as rise 1 / run 0: use UPM as the rise so the
    # run keeps its precision)
    if hh.caretSlopeRise < hd.unitsPerEm // 2: hh.caretSlopeRise = hd.unitsPerEm
    hh.caretSlopeRun = -round(hh.caretSlopeRise * t)
    # every table the slant does not need to touch goes back as its original bytes
    from fontTools.ttLib.tables.DefaultTable import DefaultTable
    if a.version:                       # own version + date, so apps don't reuse a cached build
        from fontTools.misc.timeTools import timestampNow
        old = '%.3f' % hd.fontRevision
        hd.fontRevision = float(a.version); hd.modified = timestampNow()
        for rec in o['name'].names:
            if rec.nameID == 5: rec.string = f'Version {a.version}'
            # unique ID (e.g. 'RasmeeThaana-Regular;1.007') carries the version too
            elif rec.nameID == 3 and rec.toUnicode().endswith(';' + old):
                rec.string = rec.toUnicode()[:-len(old)] + a.version
    for tag in raw.reader.keys():
        if tag in ('glyf', 'loca', 'hmtx', 'head', 'hhea', 'maxp') or (a.version and tag == 'name') or (gpos_changed and tag == 'GPOS'): continue
        d = DefaultTable(tag); d.data = raw.reader[tag]; o[tag] = d
    # post.italicAngle (Fixed 16.16 at byte 4) patched in place; rest of post stays byte-identical
    import struct
    pd = bytearray(o['post'].data); pd[4:8] = struct.pack('>i', round(a.angle * 65536))
    o['post'].data = bytes(pd)
    o.save(a.out)
    print(f'slanted {len(targets)} Thaana glyphs by {a.angle} deg (lean left) about y={c}')


if __name__ == '__main__':
    main()
