"""Detail overlays (reference grey, candidate translucent blue) for every glyph with fitted edges, drawn from a
compiled font, plus a manifest recording the input font's SHA-256.
usage: detail_plates.py font.ttf OUTDIR [--ref Faruma.ttf]   (unknown options rejected; exit 1 on any failure)
The plates and their manifest are rendered into a staging directory and published together by swapping OUTDIR, so
a failed rerun leaves the previous complete set (plates + manifest) in place. OUTDIR must be new or hold only a
previous plate set (8 PNGs + plates_manifest.json); a directory with any other file is refused, never replaced.
The existing directory's permissions are kept; a new directory gets 0777 minus the caller's umask, as mkdir would."""
import sys, os, hashlib, json

for _s in (sys.stdout, sys.stderr):   # diagnostics never fail on a non-UTF-8 console: unencodable text is escaped
    try: _s.reconfigure(errors='backslashreplace')
    except Exception: pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw
from raster import draw_glyph

PLATES = {  # glyph: (scale, x0, y0, x1, y1) in font units
    'uni0782': (0.3, -300, -400, 1600, 1950), 'uni078D': (0.3, -300, -400, 1600, 1950),
    'uni0797': (0.3, -300, -400, 1600, 1950), 'uni07AD': (0.3, -300, -400, 1600, 1950),
    'uni07AE': (0.3, -300, -400, 1600, 1950), 'uni07AF': (0.3, -300, -400, 1600, 1950),
    'afii57407': (0.4, -50, 200, 950, 1900), 'uniFDF2': (0.3, -300, -100, 1900, 2000),
}


def plate(R, N, name, out, s, x0, y0, x1, y1):
    W = int((x1 - x0) * s); H = int((y1 - y0) * s)
    im = Image.new('RGBA', (W, H), 'white'); d = ImageDraw.Draw(im)
    for gx in range((x0 // 100) * 100, x1, 100):
        d.line([((gx - x0) * s, 0), ((gx - x0) * s, H)], fill=(235, 235, 235) if gx % 500 else (200, 200, 200))
    for gy in range((y0 // 100) * 100, y1, 100):
        d.line([(0, (y1 - gy) * s), (W, (y1 - gy) * s)], fill=(235, 235, 235) if gy % 500 else (200, 200, 200))
    for f, col in ((R, (150, 150, 150, 255)), (N, (40, 90, 220, 150))):
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); draw_glyph(lay, f, name, -x0 * s, y1 * s, s, fill=col); im.alpha_composite(lay)
    d.text((4, 4), f'{name}  grey = Faruma, blue = candidate', fill=(0, 0, 0))
    im.convert('RGB').save(out)


def main():
    from font_checks import strict_parser, validate_sfnt, FontInvalid
    ap = strict_parser('detail_plates.py'); ap.add_argument('font'); ap.add_argument('outdir')
    ap.add_argument('--ref', default=os.path.join(ROOT, 'reference', 'Faruma.ttf'))
    a = ap.parse_args(); font, outdir, ref = a.font, a.outdir, a.ref
    for label, p in (('font', font), ('reference', ref)):
        if not os.path.isfile(p): print(f'FAIL: {label} not found: {p}'); sys.exit(1)
        try: validate_sfnt(p)
        except FontInvalid as e: print(f'FAIL: sfnt: {p}: {e}'); sys.exit(1)
    import tempfile, shutil
    outdir = os.path.abspath(outdir)
    if os.path.exists(outdir) and not os.path.isdir(outdir):
        print(f'FAIL: output path {outdir} exists and is not a directory'); sys.exit(1)
    owned = {f'{n}_vs_reference.png' for n in PLATES} | {'plates_manifest.json'}
    if os.path.isdir(outdir):
        other = sorted(set(os.listdir(outdir)) - owned)
        if other:   # never replace a directory that holds anything besides a previous plate set
            print(f'FAIL: {outdir} contains files other than detail plates ({other[:5]}); '
                  f'use a dedicated plates directory (nothing changed)'); sys.exit(1)
    _um = os.umask(0); os.umask(_um)   # a new directory gets the caller's umask, like mkdir
    mode = (os.stat(outdir).st_mode & 0o7777) if os.path.isdir(outdir) else (0o777 & ~_um)
    R, N = TTFont(ref), TTFont(font)
    for n in PLATES:
        for label, f in (('font', N), ('reference', R)):
            if n not in f.getGlyphOrder(): print(f'FAIL: glyph {n} missing from {label}'); sys.exit(1)
    parent = os.path.dirname(outdir); os.makedirs(parent, exist_ok=True)
    stage = tempfile.mkdtemp(prefix='.' + os.path.basename(outdir) + '.', dir=parent)
    os.chmod(stage, 0o700)
    try:
        # render the complete set (plates + manifest) into a staging directory first
        for n, (s, *box) in PLATES.items():
            plate(R, N, n, os.path.join(stage, f'{n}_vs_reference.png'), s, *box)
        man = {'font': os.path.abspath(font), 'font_sha256': hashlib.sha256(open(font, 'rb').read()).hexdigest(),
               'reference_sha256': hashlib.sha256(open(ref, 'rb').read()).hexdigest(), 'plates': sorted(PLATES)}
        json.dump(man, open(os.path.join(stage, 'plates_manifest.json'), 'w', encoding='utf-8'), indent=1)
        if os.path.isdir(outdir):   # publish plates and manifest together: swap the whole directory
            old = outdir + '.old-' + os.path.basename(stage)
            os.rename(outdir, old)
            try: os.rename(stage, outdir)
            except Exception:
                os.rename(old, outdir); raise
            for root_, dirs_, files_ in os.walk(old):   # a read-only previous set must still be removable
                os.chmod(root_, 0o700)
                for f_ in files_: os.chmod(os.path.join(root_, f_), 0o600)
            shutil.rmtree(old, ignore_errors=True)
            if os.path.exists(old):
                print(f'WARNING: the previous plate set could not be removed and remains at {old}')
        else:
            os.rename(stage, outdir)
        os.chmod(outdir, mode)   # existing directory's permissions, or the umask default for a new one
    finally:
        if os.path.isdir(stage): shutil.rmtree(stage, ignore_errors=True)
    print('plates for', man['font_sha256'], '->', outdir)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f'FAIL internal: {e!r}'); sys.exit(1)
