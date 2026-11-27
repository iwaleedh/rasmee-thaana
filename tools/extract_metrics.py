"""Extract the functional metrics (not outlines) from the reference font into spec/metrics.json:
advance widths, glyph bounding boxes (size/position targets), vertical metrics, kerning, composite offsets."""
import json, sys
from fontTools.ttLib import TTFont
f=TTFont(sys.argv[1] if len(sys.argv)>1 else 'reference/Faruma.ttf')
g=f['glyf']; hm=f['hmtx']; os2=f['OS/2']; hh=f['hhea']
out={'upm':f['head'].unitsPerEm,
 'vertical':{'hhea_ascent':hh.ascent,'hhea_descent':hh.descent,'hhea_lineGap':hh.lineGap,
   'typoAscender':os2.sTypoAscender,'typoDescender':os2.sTypoDescender,'typoLineGap':os2.sTypoLineGap,
   'winAscent':os2.usWinAscent,'winDescent':os2.usWinDescent,'xHeight':getattr(os2,'sxHeight',0),'capHeight':getattr(os2,'sCapHeight',0),
   'underlinePosition':f['post'].underlinePosition,'underlineThickness':f['post'].underlineThickness,
   'strikeoutSize':os2.yStrikeoutSize,'strikeoutPosition':os2.yStrikeoutPosition},
 'cmap':{f"{c:04X}":n for c,n in sorted(f.getBestCmap().items())},
 'glyphs':{}, 'kern':[], 'gpos_kern':[], 'composites':{}}
for n in f.getGlyphOrder():
    gl=g[n]; gl.recalcBounds(g) if hasattr(gl,'recalcBounds') else None
    bb=[gl.xMin,gl.yMin,gl.xMax,gl.yMax] if gl.numberOfContours!=0 else None
    out['glyphs'][n]={'adv':hm[n][0],'lsb':hm[n][1],'bbox':bb}
    if gl.isComposite(): out['composites'][n]=[[c.glyphName,c.x,c.y] for c in gl.components]
for st in f['kern'].kernTables:
    for (l,r),v in st.kernTable.items(): out['kern'].append([l,r,v])
for lk in f['GPOS'].table.LookupList.Lookup:
    for st in lk.SubTable:
        if st.Format==1:
            for first,ps in zip(st.Coverage.glyphs, st.PairSet):
                for rec in ps.PairValueRecord: out['gpos_kern'].append([first,rec.SecondGlyph,rec.Value1.XAdvance])
json.dump(out,open('spec/metrics.json','w'),indent=1)
print(len(out['glyphs']),'glyphs',len(out['kern']),'kern',len(out['gpos_kern']),'gpos pairs')
