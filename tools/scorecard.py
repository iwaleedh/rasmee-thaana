"""Aggregate a review round into one scorecard.
Per glyph: objective score (metrics.json from compare.py) + every reviewer JSON in the round dir
(sol.json, gemini.json, opus.json ...). Final glyph score = the LOWEST of all scores (a glyph is only
10/10 when every reviewer and the objective check agree).  usage: scorecard.py review/rN"""
import sys, os, json, glob

d = sys.argv[1]
obj = json.load(open(os.path.join(d, 'metrics.json')))


INTENT = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'spec', 'intentional.json')))


def objective(m, g=None):
    w = abs(m['weight'] - 1.0); b = max(abs(x) for x in m['bbox_delta']); s = m['sim']
    if g in INTENT:  # documented, deliberate deviation for collision safety: judge colour only
        b = 0; s = max(s, 0.955)
    score = 10.0
    score -= max(0, (w - 0.06) * 25)        # colour within ±6% is perfect
    score -= max(0, (b - 12) / 12)          # bbox within 12u is perfect
    score -= max(0, (0.955 - s) * 60)       # massing similarity ≥0.955 is perfect
    return round(max(0, min(10, score)), 1)


revs = {}
for p in sorted(glob.glob(os.path.join(d, '*.json'))):
    n = os.path.basename(p)[:-5]
    if n in ('metrics', 'scorecard', 'clearance'): continue
    try: revs[n] = json.load(open(p))
    except Exception as e: print('skip', p, e)

names = sorted(set(obj) | set(g for r in revs.values() for g in r.get('glyphs', {})))
rows = {}
for g in names:
    r = {'objective': objective(obj[g], g) if g in obj else None}
    for n, rv in revs.items():
        e = rv.get('glyphs', {}).get(g)
        if e: r[n] = e.get('overall'); r[n + '_fix'] = e.get('fix', '')
    vals = [v for k, v in r.items() if not k.endswith('_fix') and isinstance(v, (int, float))]
    r['final'] = min(vals) if vals else None
    rows[g] = r
font = {n: rv.get('font', {}) for n, rv in revs.items()}
json.dump({'glyphs': rows, 'font': font}, open(os.path.join(d, 'scorecard.json'), 'w'), indent=1, ensure_ascii=False)
cols = ['objective'] + list(revs)
print(f"{'glyph':12s} " + ' '.join(f'{c[:8]:>8s}' for c in cols) + '    final')
for g, r in rows.items():
    print(f'{g:12s} ' + ' '.join(f"{(r.get(c) if r.get(c) is not None else '-'):>8}" for c in cols) + f"    {r['final']}")
fin = [r['final'] for r in rows.values() if r['final'] is not None]
print('glyphs at 10:', sum(1 for v in fin if v >= 10), '/', len(fin), ' mean', round(sum(fin) / len(fin), 2))
for n, f in font.items(): print(n, 'font:', f)
