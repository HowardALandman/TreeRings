import json, os, glob, collections, brotli, re, math
V='web/data/values'
ix=json.loads(brotli.decompress(open('web/data/index.json','rb').read()))
meta={s['code'].lower():s for s in ix['sites']}
logs={}
for p in glob.glob(V+'/*.json'):
    site=os.path.basename(p)[:-5]
    for sid,d in json.load(open(p)).items(): logs[(site,sid)]=(d['f'],d['u'],d['v'])
nsite=collections.Counter(k[0] for k in logs)
bysite=collections.defaultdict(list)
for k in logs: bysite[k[0]].append(k)
G=ix['groups']
# group actually drawn per site: recompute from GENUS mapping in corpus
import sys; sys.path.insert(0,'.')
from ehd import corpus
print('== species code (from study name) vs template Species_Name genus')
bad=[]
for s,m in meta.items():
    lat=(m['latin'] or '').split(' ')[0]
    if not m['species'] and not lat: continue
    g=m['genus']
    if lat and g and lat.lower()!=g.lower(): bad.append((s,nsite[s],m['species'],g,m['latin'],corpus.classify(m['species'])[1]))
    elif lat and not g: bad.append((s,nsite[s],m['species'],'(unmapped code)',m['latin'],corpus.classify(m['species'])[1]))
mis=[b for b in bad if b[3]!='(unmapped code)']
print(' genus MISMATCH:',len(mis),'sites',sum(b[1] for b in mis),'logs'); [print('   ',b) for b in mis]
un=collections.Counter(); unl=collections.Counter()
for b in bad:
    if b[3]=='(unmapped code)': un[(b[2][:2],b[4].split(' ')[0])]+=1; unl[(b[2][:2],b[4].split(' ')[0])]+=b[1]
print(' codes with no genus mapping (drawn as "other"):',[(k,v,unl[k]) for k,v in un.most_common()])
print(' no latin name:',[(s,m['species']) for s,m in meta.items() if not m['latin']][:20])
# ITA072 vs ital050
a={i for (s,i) in bysite['ita072be100']}; b={i for (s,i) in bysite['ital050']}
print('\n== ita072be100 ids',sorted(a)[:6],len(a),'ital050 ids',sorted(b)[:6],len(b),'common',len(a&b), '| coords',meta['ita072be100']['lat'],meta['ita072be100']['lon'],meta['ital050']['lat'],meta['ital050']['lon'])
for fam in ('ita072','ita073','ita074'):
    fs=sorted(s for s in meta if s.startswith(fam) and s!=fam)
    spans=[{(i,logs[(s,i)][0],len(logs[(s,i)][2])) for (_,i) in bysite[s]} for s in fs]
    print(' ',fam,'BI files',len(fs),'logs each',[len(x) for x in spans],'all identical id+span sets:',all(x==spans[0] for x in spans), '| base ids in BI ids:', len({i for _,i in bysite.get(fam,[])}&{i for i,_,_ in spans[0]}),'of',nsite.get(fam,0))
# scale-invariant duplicates among sites within 3 km
def km(a,b,c,d): return 111*math.hypot(a-c,(b-d)*math.cos(math.radians((a+c)/2)))
ss=[s for s in meta if meta[s]['lat'] is not None]
grid=collections.defaultdict(list)
for s in ss: grid[(round(meta[s]['lat']*10),round(meta[s]['lon']*10))].append(s)
near=set()
for (gy,gx),l in grid.items():
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            for t in grid.get((gy+dy,gx+dx),[]):
                for s in l:
                    if s<t and km(meta[s]['lat'],meta[s]['lon'],meta[t]['lat'],meta[t]['lon'])<=3: near.add((s,t))
print('\n== site pairs within 3 km:',len(near))
def corr(a,b):
    fa,ua,va=logs[a]; fb,ub,vb=logs[b]; lo=max(fa,fb); hi=min(fa+len(va),fb+len(vb))
    xs=[];ys=[]
    for y in range(lo,hi):
        x=va[y-fa]; z=vb[y-fb]
        if x is None or z is None or x<=0 or z<=0: continue
        xs.append(x*ua); ys.append(z*ub)
    n=len(xs)
    if n<30: return None
    mx=sum(xs)/n; my=sum(ys)/n
    sx=sum((x-mx)**2 for x in xs); sy=sum((y-my)**2 for y in ys)
    if sx==0 or sy==0: return None
    r=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/math.sqrt(sx*sy)
    return r,n,my/mx
exact={(tuple(a),tuple(b)) for a,b,*_ in json.load(open('/tmp/ehd_pairs.json'))}
found=collections.defaultdict(list)
for s,t in sorted(near):
    if nsite[s]*nsite[t]>60000: continue
    for a in bysite[s]:
        for b in bysite[t]:
            if (a,b) in exact or (b,a) in exact: continue
            c=corr(a,b)
            if c and c[0]>0.995: found[(s,t)].append((a[1],b[1],round(c[0],4),c[1],round(c[2],3)))
print(' site pairs with series correlated r>0.995 (not already exact duplicates):',len(found))
for (s,t),l in sorted(found.items(), key=lambda kv:-len(kv[1])):
    ratios=collections.Counter(round(x[4],1) for x in l)
    print(f'   {s}({nsite[s]}) {t}({nsite[t]}) pairs {len(l)} scale ratios {ratios.most_common(3)} | {meta[s]["site"][:26]} / {meta[t]["site"][:26]} | {meta[s]["variant"]} / {meta[t]["variant"]} | e.g. {l[0]}')
# within-site high correlation (same tree measured twice at different scale?) skip
# tree estimate
trees=0; multi=collections.Counter()
for s,ks in bysite.items():
    stems=collections.Counter()
    for _,i in ks:
        j=i.strip()
        m=re.match(r'^(.*\d)[A-Za-z]$',j)
        stems[m.group(1) if m else j]+=1
    trees+=len(stems); multi[s]=nsite[s]/len(stems)
print('\n== rough tree count if a trailing letter is a core label:',trees,'of',len(logs),'series')
print(' short series <10 rings by site:',collections.Counter(k[0] for k,(f,u,v) in logs.items() if len(v)<10).most_common(12))
