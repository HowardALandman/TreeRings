import json, os, glob, collections, brotli, re, statistics, math
V='web/data/values'
ix=json.loads(brotli.decompress(open('web/data/index.json','rb').read()))
meta={s['code'].lower():s for s in ix['sites']}
logs={}
for p in glob.glob(V+'/*.json'):
    site=os.path.basename(p)[:-5]
    for sid,d in json.load(open(p)).items(): logs[(site,sid)]=(d['f'],d['u'],d['v'])
nsite=collections.Counter(k[0] for k in logs)
print('== variant labels:',collections.Counter(m['variant'] for m in meta.values()))
print('== dating:',collections.Counter(m['dating'] for m in meta.values()))
# 1 same (id,first,len) across sites with different values (ITA-style)
sig=collections.defaultdict(set)
for (s,i),(f,u,v) in logs.items(): sig[(i.strip().upper(),f,len(v))].add(s)
pc=collections.Counter()
for k,ss in sig.items():
    ss=sorted(ss)
    for a in range(len(ss)):
        for b in range(a+1,len(ss)): pc[(ss[a],ss[b])]+=1
dup=json.load(open('/tmp/ehd_pairs.json'))
vd=collections.Counter()
for a,b,*_ in dup:
    if a[0]!=b[0]: vd[tuple(sorted((a[0],b[0])))]+=1
print('\n== site pairs sharing >=5 (id,start,length) signatures but NOT value-duplicates:')
fam=collections.defaultdict(set)
for (a,b),c in sorted(pc.items(), key=lambda kv:-kv[1]):
    if c>=5 and vd[(a,b)]<c/2:
        fam[re.match(r'[a-z]+\d+',a).group(0)].update((a,b))
        if not (a.startswith('ita07') and b.startswith('ita07')): print('  ',a,nsite[a],b,nsite[b],'shared sigs',c,'value-dups',vd[(a,b)],'|',meta[a]['site'],'|',meta[b]['site'],'|',meta[a]['variant'])
for k,v in fam.items(): print('  family',k,sorted(v),'logs',sum(nsite[s] for s in v))
# 2 value sanity
print('\n== value sanity')
big=[];zero=[];const=[];short=[];long_=[];future=[];gappy=[]
for k,(f,u,v) in logs.items():
    vals=[x for x in v if x is not None]
    if not vals: zero.append(k); continue
    mx=max(vals)*u
    if mx>25: big.append((round(mx,2),k,u))
    if len(set(vals))==1 and len(vals)>10: const.append(k)
    if len(v)<10: short.append((len(v),k))
    if len(v)>1500: long_.append((len(v),k,f))
    if f+len(v)-1>2024: future.append((f+len(v)-1,k))
    nn=sum(x is None for x in v)
    if nn/len(v)>0.3: gappy.append((round(nn/len(v),2),len(v),k))
print(' no values',len(zero),zero[:5]); print(' max ring >25mm:',len(big),sorted(big,reverse=True)[:25])
c=collections.Counter(k[0] for _,k,_ in big); print('   by site',c.most_common(15))
print(' constant',const[:10]); print(' <10 rings',len(short),sorted(short)[:15]); print(' >1500 rings',sorted(long_,reverse=True)[:15]); print(' ends after 2024',future[:10]); print(' >30% missing',len(gappy),sorted(gappy,reverse=True)[:12])
# site median ring width: unit errors
med={}
for s in nsite:
    vals=[x*u for (ss,i),(f,u,v) in logs.items() if ss==s for x in v if x] if False else None
bys=collections.defaultdict(list)
for (s,i),(f,u,v) in logs.items():
    vv=[x*u for x in v if x]; 
    if vv: bys[s].append(statistics.median(vv))
sm={s:statistics.median(v) for s,v in bys.items()}
lo=sorted((m,s) for s,m in sm.items())
print(' site median ring width mm: smallest',[(round(m,3),s,meta[s]['variant'],meta[s]['species']) for m,s in lo[:12]])
print(' largest',[(round(m,2),s,meta[s]['variant'],meta[s]['species']) for m,s in lo[-30:]])
# 3 metadata sanity
print('\n== metadata')
print(' no species group/code:',[(s,nsite[s]) for s,m in meta.items() if not m['species']][:30])
print(' empty site name:',[s for s,m in meta.items() if not m['site']][:20], ' empty location:',[s for s,m in meta.items() if not m['location']][:20])
loc=collections.defaultdict(collections.Counter)
for s,m in meta.items(): loc[re.match(r'[a-z]+',s).group(0)][m['location']]+=1
for p,c in sorted(loc.items()):
    if len(c)>1: print('  prefix',p,dict(c))
# coordinate outliers vs same-prefix median
byp=collections.defaultdict(list)
for s,m in meta.items():
    if m['lat'] is not None: byp[re.match(r'[a-z]+',s).group(0)].append((m['lat'],m['lon'],s))
def km(a,b,c,d): return 111*math.hypot(a-c,(b-d)*math.cos(math.radians((a+c)/2)))
out=[]
for p,l in byp.items():
    if len(l)<4: continue
    la=statistics.median(x[0] for x in l); lo_=statistics.median(x[1] for x in l)
    ds=sorted(km(x[0],x[1],la,lo_) for x in l); q=ds[int(.9*(len(ds)-1))]
    for x in l:
        d=km(x[0],x[1],la,lo_)
        if d>max(3*q,600): out.append((round(d),x[2],x[0],x[1],meta[x[2]]['location'],meta[x[2]]['site']))
print(' coordinate outliers vs country-prefix median:',sorted(out,reverse=True)[:25])
# 4 id prefix heterogeneity for compilation suspects
for s in ('aust115','fran049','finl077','brit065','neth025','neth031','fran10','swed334','swit313','swit312'):
    c=collections.Counter(re.sub(r'\d.*$','',i[:6]) for (ss,i) in logs if ss==s)
    c2=collections.Counter(i[:5] for (ss,i) in logs if ss==s)
    print(' ',s,nsite[s],meta[s]['species'],meta[s]['site'][:40],'| id stems',c.most_common(14) if len(c)<60 else len(c), '|', c2.most_common(8))
