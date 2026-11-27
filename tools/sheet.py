"""Glyph review sheet: one cell per glyph, reference (grey) under candidate (colour), with metric lines.
usage: sheet.py out.png ref.ttf [cand.ttf] [--cps 0780-07A5] [--scale 0.12]"""
import sys, argparse
sys.path.insert(0, __file__.rsplit('/',1)[0])
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont
from raster import draw_glyph
ap=argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('ref'); ap.add_argument('cand',nargs='?')
ap.add_argument('--cps',default='0780-07A5'); ap.add_argument('--scale',type=float,default=0.12); ap.add_argument('--cols',type=int,default=8)
ap.add_argument('--names',default=None); ap.add_argument('--nolabel',action='store_true')
a=ap.parse_args()
ref=TTFont(a.ref); cand=TTFont(a.cand) if a.cand else None
cm=ref.getBestCmap()
if a.names: names=a.names.split(',')
else:
    lo,hi=[int(x,16) for x in a.cps.split('-')]; names=[cm[c] for c in range(lo,hi+1) if c in cm]
s=a.scale; cw=int(2300*s)+20; ch=int(3200*s)+40
cols=min(a.cols,len(names)); rows=(len(names)+cols-1)//cols
img=Image.new('RGBA',(cols*cw,rows*ch),(255,255,255,255)); d=ImageDraw.Draw(img)
try: fnt=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',14)
except: fnt=None
for i,n in enumerate(names):
    cx=(i%cols)*cw; cy=(i//cols)*ch
    ox=cx+int(500*s)+10; oy=cy+int(2000*s)+20
    adv=ref['hmtx'][n][0]
    for y,col in [(0,(255,0,0)),(1900,(200,200,255)),(-1100,(200,200,255))]:
        d.line([(cx,oy-y*s),(cx+cw-4,oy-y*s)],fill=col)
    d.line([(ox,cy),(ox,cy+ch)],fill=(180,180,180)); d.line([(ox+adv*s,cy),(ox+adv*s,cy+ch)],fill=(180,180,180))
    draw_glyph(img,ref,n,ox,oy,s,fill=(0,0,0,70) if cand else (0,0,0,255))
    if cand and n in cand.getGlyphOrder():
        ca=cand['hmtx'][n][0]
        if ca!=adv: d.line([(ox+ca*s,cy),(ox+ca*s,cy+ch)],fill=(255,0,255))
        draw_glyph(img,cand,n,ox,oy,s,fill=(0,90,200,150))
    if not a.nolabel: d.text((cx+4,cy+4),n,fill=(0,0,0),font=fnt)
    d.rectangle([cx,cy,cx+cw-1,cy+ch-1],outline=(220,220,220))
img.convert('RGB').save(a.out); print(a.out, img.size)
