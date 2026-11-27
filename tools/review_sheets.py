"""Produce a review pack for a round: side-by-side glyph sheets, fili matrix, text at sizes, metrics report.
usage: review_sheets.py ROUND_DIR [font.ttf]"""
import sys, os, subprocess, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont
from raster import draw_glyph

out = sys.argv[1]; os.makedirs(out, exist_ok=True)
NEW = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'build', 'RasmeeThaana-Regular.ttf')
REF = os.path.join(ROOT, 'reference', 'Faruma.ttf')
ref, new = TTFont(REF), TTFont(NEW)
try: fnt = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 16)
except Exception: fnt = None

LETTERS = [f'uni{c:04X}' for c in range(0x780, 0x7A6)] + ['uni07B1']
FILI = [f'uni{c:04X}' for c in range(0x7A6, 0x7B1)]
OTHER = ['DotAbove', 'TwoDots', 'ThreeDots', 'uni25CC', 'afii57388', 'afii57403', 'afii57407', 'uniFDF2']

def side_by_side(names, fn, s=0.11, cols=4):
    cw = int(2 * 2300 * s) + 30; ch = int(3000 * s) + 30
    rows = (len(names) + cols - 1) // cols
    img = Image.new('RGBA', (cols * cw, rows * ch), (255, 255, 255, 255)); d = ImageDraw.Draw(img)
    for i, n in enumerate(names):
        cx = (i % cols) * cw; cy = (i // cols) * ch
        for j, (f, col) in enumerate([(ref, (90, 90, 90, 255)), (new, (0, 0, 0, 255))]):
            ox = cx + 10 + j * int(2300 * s) + int(450 * s); oy = cy + 24 + int(1950 * s)
            adv = f['hmtx'][n][0] if n in f['hmtx'].metrics else 0
            d.line([(ox - 40, oy), (ox + int(1900 * s), oy)], fill=(255, 170, 170))
            d.line([(ox, oy - int(1900 * s)), (ox, oy + int(1000 * s))], fill=(225, 225, 225))
            d.line([(ox + adv * s, oy - int(1900 * s)), (ox + adv * s, oy + int(1000 * s))], fill=(225, 225, 225))
            if n in f.getGlyphOrder(): draw_glyph(img, f, n, ox, oy, s, fill=col)
        d.text((cx + 6, cy + 4), f'{n}   ref(grey) | new(black)', fill=(0, 0, 0), font=fnt)
        d.rectangle([cx, cy, cx + cw - 1, cy + ch - 1], outline=(200, 200, 200))
    img.convert('RGB').save(os.path.join(out, fn))

side_by_side(LETTERS[:20], 'glyphs_A.png'); side_by_side(LETTERS[20:], 'glyphs_B.png')
side_by_side(FILI + OTHER, 'glyphs_C_fili_symbols.png')

def hb(font, text, size, path):
    subprocess.run(['hb-view', font, f'--font-size={size}', '--margin=24', '-o', path, text], check=True)

def stack(paths, labels, dst):
    ims = [Image.open(p).convert('RGB') for p in paths]
    W = max(i.width for i in ims) + 10; H = sum(i.height + 22 for i in ims)
    c = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(c); y = 0
    for im, lb in zip(ims, labels):
        d.text((6, y + 3), lb, fill=(200, 0, 0), font=fnt); c.paste(im, (5, y + 20)); y += im.height + 22
    c.save(dst)
    for p in paths: os.remove(p)

texts = {
 'sentences': 'ދިވެހިރާއްޖޭގެ ޖުމްހޫރިއްޔާ، ރައީސުލްޖުމްހޫރިއްޔާގެ އޮފީސް. މި ގާނޫނަކީ ދިވެހިރާއްޖޭގެ ޤާނޫނުއަސާސީގެ ދަށުން ހަދާ ގާނޫނެކެވެ.',
 'alphabet': 'ހ ށ ނ ރ ބ ޅ ކ އ ވ މ ފ ދ ތ ލ ގ ޏ ސ ޑ ޒ ޓ ޔ ޕ ޖ ޗ ޘ ޙ ޚ ޛ ޜ ޝ ޞ ޟ ޠ ޡ ޢ ޣ ޤ ޥ ޱ',
 'fili_on_haa': 'ހަ ހާ ހި ހީ ހު ހޫ ހެ ހޭ ހޮ ހޯ ހް  ސަ ސާ ސި ސީ ސު ސޫ ސެ ސޭ ސޮ ސޯ ސް',
 'mixed': 'ސަރުކާރުގެ ރަސްމީ ލިޔުން 2026 ވަނަ އަހަރު؟ ހާ؛ (Official Letter No. 12/34) “ދިވެހި” ﷽ ޱަ ޱާ ޱި ޱީ ޱު ޱޫ ޱެ ޱޭ ޱޮ ޱޯ ޱް',
}
def pil_bidi(font, text, size, path):
    # Unicode BiDi paragraph itemisation via Pillow + libraqm (FriBiDi/HarfBuzz)
    f = ImageFont.truetype(font, size, layout_engine=ImageFont.Layout.RAQM)
    l, t_, r, b = f.getbbox(text, direction='rtl')
    im = Image.new('RGB', (r - l + 48, int(size * 1.6) + 48), 'white')
    ImageDraw.Draw(im).text((24 - l, 24), text, font=f, fill='black', direction='rtl')
    im.save(path)

for k, t in texts.items():
    ps = []
    for size in ([36, 72] if k != 'sentences' else [20, 36, 72]):
        for f, lb in [(REF, 'reference'), (NEW, 'new')]:
            p = os.path.join(out, f'_{k}_{size}_{lb}.png')
            (pil_bidi if k == 'mixed' else hb)(f, t, size, p); ps.append(p)
    stack(ps, [f'{lb} {sz}px' for sz in ([36, 72] if k != 'sentences' else [20, 36, 72]) for lb in ('reference', 'new')], os.path.join(out, f'text_{k}.png'))

# fili matrix: every letter with every fili, new font
mat = '\n'.join(' '.join(chr(int(l[3:], 16)) + chr(int(f[3:], 16)) for f in FILI) for l in LETTERS)
for f, lb in [(NEW, 'new'), (REF, 'reference')]:
    subprocess.run(['hb-view', f, '--font-size=44', '--margin=24', '-o', os.path.join(out, f'fili_matrix_{lb}.png'), mat], check=True)
r = subprocess.run([os.path.join(ROOT, '.venv', 'bin', 'python'), os.path.join(ROOT, 'tools', 'compare.py'), ','.join(LETTERS + FILI + ['DotAbove', 'TwoDots', 'ThreeDots']), '--ttf', NEW, '--json', os.path.join(out, 'metrics.json')], capture_output=True, text=True)
open(os.path.join(out, 'metrics.txt'), 'w').write(r.stdout + r.stderr)
r = subprocess.run([os.path.join(ROOT, '.venv', 'bin', 'python'), os.path.join(ROOT, 'tools', 'shapecheck.py'), NEW], capture_output=True, text=True)
open(os.path.join(out, 'spacing.txt'), 'w').write(r.stdout[-2000:])
print('review pack in', out); print(sorted(os.listdir(out)))
