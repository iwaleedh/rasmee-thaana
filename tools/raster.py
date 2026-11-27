"""Rasterise glyphs from a TTF to PIL images (no shaping) for review sheets."""
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from PIL import Image, ImageDraw, ImageFont

class FlatPen(BasePen):
    def __init__(self, gs, steps=12):
        super().__init__(gs); self.contours=[]; self.cur=[]; self.steps=steps
    def _moveTo(self,p): self.cur=[p]
    def _lineTo(self,p): self.cur.append(p)
    def _curveToOne(self,a,b,c):
        p0=self.cur[-1]; n=self.steps
        for i in range(1,n+1):
            t=i/n; self.cur.append(tuple((1-t)**3*p0[k]+3*(1-t)**2*t*a[k]+3*(1-t)*t*t*b[k]+t**3*c[k] for k in (0,1)))
    def _qCurveToOne(self,a,b):
        p0=self.cur[-1]; n=self.steps
        for i in range(1,n+1):
            t=i/n; self.cur.append(tuple((1-t)**2*p0[k]+2*(1-t)*t*a[k]+t*t*b[k] for k in (0,1)))
    def _closePath(self):
        if self.cur: self.contours.append(self.cur)
        self.cur=[]
    _endPath=_closePath

def contours(font, name):
    gs=font.getGlyphSet(); p=FlatPen(gs); gs[name].draw(p); return p.contours

def draw_glyph(img, font, name, ox, oy, scale, fill=(0,0,0,255)):
    """ox,oy = pixel position of glyph origin (baseline-left). y up in font."""
    layer=Image.new('L', img.size, 0); d=ImageDraw.Draw(layer)
    # even-odd via XOR compositing of each contour
    from PIL import ImageChops
    for c in contours(font,name):
        if len(c)<3: continue
        m=Image.new('L', img.size, 0); ImageDraw.Draw(m).polygon([(ox+x*scale, oy-y*scale) for x,y in c], fill=255)
        layer=ImageChops.logical_xor(layer.convert('1'), m.convert('1')).convert('L')
    col=Image.new('RGBA', img.size, fill); img.alpha_composite(Image.composite(col, Image.new('RGBA',img.size,(0,0,0,0)), layer))
