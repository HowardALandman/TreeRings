import json, os, glob, collections, brotli
V='web/data/values'
ix=json.loads(brotli.decompress(open('web/data/index.json','rb').read()))
meta={s['code'].lower():s for s in ix['sites']}
logs={}
for p in glob.glob(V+'/*.json'):
    site=os.path.basename(p)[:-5]
    for sid,d in json.load(open(p)).items(): logs[(site,sid)]=(d['f'],d['u'],d['v'])
nsite=collections.Counter(k[0] for k in logs)
W=15
def mic(x,u): return None if x is None else round(x*u*1000)
cand=collections.defaultdict(set)
# aligned windows (complete for same-dated copies) + content-sampled (shifted copies)
fa=collections.defaultdict(list); fs=collections.defaultdict(list)
for k,(f,u,v) in logs.items():
    m=[mic(x,u) for x in v]
    for i in range(0,len(m)-W+1):
        w=tuple(m[i:i+W])
        if any(x is None or x<=0 for x in w): continue
        if (f+i)%5==0: fa[(f+i,w)].append(k)
        if hash(w)%8==0: fs[w].append((k,f+i))
pairs={}
for key,l in fa.items():
    l=sorted(set(l))
    if 1<len(l)<=40:
        for a in range(len(l)):
            for b in range(a+1,len(l)): pairs[(l[a],l[b])]=0
nshift=collections.Counter()
for w,l in fs.items():
    d={}
    for k,y in l: d.setdefault(k,y)
    it=sorted(d.items())
    if 1<len(it)<=40:
        for a in range(len(it)):
            for b in range(a+1,len(it)):
                o=it[b][1]-it[a][1]
                if o!=0:
                    nshift[(it[a][0],it[b][0],o)]+=1
print('candidate same-dated pairs',len(pairs),' shifted-window hits',len(nshift))
def cmp(a,b,o=0):
    fa_,ua,va=logs[a]; fb_,ub,vb=logs[b]; fb_-=o
    lo=max(fa_,fb_); hi=min(fa_+len(va),fb_+len(vb)); n=eq=0
    for y in range(lo,hi):
        x=mic(va[y-fa_],ua); z=mic(vb[y-fb_],ub)
        if x is None or z is None: continue
        n+=1; eq+= x==z
    return n,eq,len(va),len(vb)
res=[]
for (a,b) in pairs:
    n,eq,la,lb=cmp(a,b)
    if n>=20 and eq/n>=0.9: res.append((a,b,n,eq,la,lb))
print('same-dated duplicate pairs (>=20 yr overlap, >=90% identical):',len(res))
kind=collections.Counter()
for a,b,n,eq,la,lb in res:
    kind['identical whole series' if (eq==n==la==lb) else 'one contains the other' if eq==n and n==min(la,lb) else 'identical on overlap, each has extra' if eq==n else 'edited (90-99.9% equal)']+=1
print(kind)
# components
par={}
def find(x):
    while par.setdefault(x,x)!=x: par[x]=par[par[x]]; x=par[x]
    return x
for a,b,*_ in res: par[find(a)]=find(b)
comp=collections.defaultdict(list)
for x in list(par): comp[find(x)].append(x)
red=sum(len(c)-1 for c in comp.values())
print('duplicate clusters',len(comp),'logs involved',sum(map(len,comp.values())),'REDUNDANT logs',red, f'= {red/len(logs):.2%} of {len(logs)}')
print('cluster sizes',sorted(collections.Counter(map(len,comp.values())).items()))
rings=sum(len(logs[x][2]) for c in comp.values() for x in sorted(c,key=lambda x:-len(logs[x][2]))[1:])
print('redundant ring-years',rings, f'of {sum(len(v[2]) for v in logs.values())}')
# site-pair table
sp=collections.defaultdict(lambda:[set(),set(),0])
wsite=collections.Counter()
for a,b,n,eq,la,lb in res:
    if a[0]==b[0]: wsite[a[0]]+=1; continue
    k=tuple(sorted((a[0],b[0]))); e=sp[k]
    (e[0] if a[0]==k[0] else e[1]).add(a); (e[0] if b[0]==k[0] else e[1]).add(b); e[2]+= a[1]==b[1]
print('\nsite pairs:',len(sp))
def d(s): m=meta[s]; return f"{m['site'][:28]}|{m['species']}|{m['lat']},{m['lon']}|{m['who'][:22]}|{m['url'].rsplit('/',1)[-1]}"
rows=sorted(sp.items(), key=lambda kv:-min(len(kv[1][0]),len(kv[1][1])))
for (s1,s2),(A,B,same) in rows:
    print(f"{s1:>10}({len(A):4d}/{nsite[s1]:4d})  {s2:>18}({len(B):4d}/{nsite[s2]:4d}) sameID {same:4d} | {d(s1)}  ||  {d(s2)}")
print('\nwithin-site duplicate pairs:',sum(wsite.values()),'in',len(wsite),'sites',wsite.most_common())
print('\nshifted (same rings, different years):')
sh=collections.defaultdict(int)
for (a,b,o),c in nshift.items():
    n,eq,la,lb=cmp(a,b,o)
    if n>=20 and eq/n>=0.9: print('  ',a,logs[a][0],la,'|',b,logs[b][0],lb,'| offset',o,'overlap',n,'equal',eq)
json.dump([[list(a),list(b),n,eq,la,lb] for a,b,n,eq,la,lb in res], open('/tmp/ehd_pairs.json','w'))
