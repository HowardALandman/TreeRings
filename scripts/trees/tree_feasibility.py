"""Feasibility: can series be grouped into trees/timbers, and does ring-width
correlation independently confirm the grouping?

Reads the built web/data/values shards; run from the repo root.
usage: .venv/bin/python scripts/trees/tree_feasibility.py [per_site.json]
Detrend: first difference of log width (removes age trend, keeps the
year-to-year signal that crossdating rests on). Pearson r on overlap >= MINOV.
"""
import json, glob, os, re, math, random, collections, sys

V = 'web/data/values'
MINOV = 30
random.seed(0)

def tree_key(sid):
    m = re.match(r'^(.*\d)([A-Za-z]{1,2})$', sid)
    if m:
        return m.group(1), 'letter'
    if re.fullmatch(r'\d{6,7}', sid):
        return sid[:-1], 'schweingruber'
    return sid, 'none'

def series(d):
    f, v = d['f'], d['v']
    out = {}
    for i in range(1, len(v)):
        a, b = v[i - 1], v[i]
        if a is None or b is None or a <= 0 or b <= 0:
            continue
        out[f + i] = math.log(b) - math.log(a)
    return out

def corr(x, y):
    ks = x.keys() & y.keys()
    n = len(ks)
    if n < MINOV:
        return None, n
    xs = [x[k] for k in ks]; ys = [y[k] for k in ks]
    mx = sum(xs) / n; my = sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs); syy = sum((b - my) ** 2 for b in ys)
    if sxx == 0 or syy == 0:
        return None, n
    return sxy / math.sqrt(sxx * syy), n

within, between = [], []
kinds = collections.Counter()
grouped_series = 0; total = 0
best_is_sibling = collections.Counter()
per_site = []
no_overlap_sib = 0
for p in sorted(glob.glob(V + '/*.json')):
    site = os.path.basename(p)[:-5]
    d = json.load(open(p))
    ids = sorted(d)
    total += len(ids)
    keys = {s: tree_key(s) for s in ids}
    # SSSTTC only if the trailing digit behaves like a core number (small, repeated)
    last = {s[-1] for s in ids if keys[s][1] == 'schweingruber'}
    if last and not last <= set('0123'):
        keys = {s: ((s, 'none') if k[1] == 'schweingruber' else k) for s, k in keys.items()}
    for s in ids:
        kinds[keys[s][1]] += 1
    groups = collections.defaultdict(list)
    for s in ids:
        groups[keys[s][0]].append(s)
    multi = {k: g for k, g in groups.items() if len(g) > 1}
    grouped_series += sum(len(g) for g in multi.values())
    if not multi:
        continue
    S = {s: series(d[s]) for s in ids}
    w_site, b_site = [], []
    for g in multi.values():
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                r, n = corr(S[g[i]], S[g[j]])
                if r is None:
                    no_overlap_sib += 1
                else:
                    w_site.append(r)
    # between-tree sample
    pairs = [(a, b) for a in ids for b in ids if a < b and keys[a][0] != keys[b][0]]
    for a, b in random.sample(pairs, min(len(pairs), 200)):
        r, n = corr(S[a], S[b])
        if r is not None:
            b_site.append(r)
    within += w_site; between += b_site
    # independent check: for each grouped series, is its best partner (max r
    # over the whole collection, capped at 300 candidates) an ID sibling?
    cand = ids if len(ids) <= 300 else random.sample(ids, 300)
    for g in multi.values():
        for s in g:
            best, br = None, -2
            for t in set(cand) | set(g):
                if t == s:
                    continue
                r, n = corr(S[s], S[t])
                if r is not None and r > br:
                    best, br = t, r
            if best is not None:
                best_is_sibling[keys[best][0] == keys[s][0]] += 1
    if w_site and b_site:
        per_site.append((site, len(ids), len(w_site), sorted(w_site)[len(w_site)//2],
                         sorted(b_site)[len(b_site)//2]))

def q(xs, ps=(0.05, 0.25, 0.5, 0.75, 0.95)):
    xs = sorted(xs)
    return ' '.join(f'{xs[int(p*(len(xs)-1))]:.2f}' for p in ps)

print(f'series {total}; ID-key kinds {dict(kinds)}')
print(f'series in an ID group of >=2: {grouped_series} ({grouped_series/total:.1%})')
print(f'sibling pairs with <{MINOV} yr overlap (untestable): {no_overlap_sib}')
print(f'within-ID-group r  n={len(within):6d}  q05/25/50/75/95 = {q(within)}')
print(f'between-group r    n={len(between):6d}  q05/25/50/75/95 = {q(between)}')
print(f'best partner is ID sibling: {dict(best_is_sibling)}  '
      f'= {best_is_sibling[True]/sum(best_is_sibling.values()):.1%}')
# separation per site: median within minus median between
per_site.sort(key=lambda r: r[3] - r[4])
print(f'\nsites tested {len(per_site)}; weakest separation (median within - median between):')
for r in per_site[:15]:
    print(f'  {r[0]:>12} n={r[1]:4d} sibpairs={r[2]:4d} within={r[3]:.2f} between={r[4]:.2f}')
if len(sys.argv) > 1:
    json.dump(per_site, open(sys.argv[1], 'w'))
