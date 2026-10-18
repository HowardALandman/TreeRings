import json, brotli, urllib.request, concurrent.futures as cf, time, sys
ix=json.loads(brotli.decompress(open('web/data/index.json','rb').read()))
ids=sorted({s['url'].rsplit('/',1)[-1] for s in ix['sites'] if s['url']})
print('study ids',len(ids),'sites without url',[s['code'] for s in ix['sites'] if not s['url']],flush=True)
def get(i):
    for k in range(4):
        try:
            d=json.load(urllib.request.urlopen(f"https://www.ncei.noaa.gov/access/paleo-search/study/search.json?NOAAStudyId={i}",timeout=90))
            st=d.get('study') or []
            if not st: return i,None
            s=st[0]
            files=[f.get('fileUrl','').rsplit('/',1)[-1] for site in s.get('site') or [] for pd in site.get('paleoData') or [] for f in pd.get('dataFile') or []]
            return i,{'name':s.get('studyName'),'notes':s.get('studyNotes') or '','files':files}
        except Exception as e:
            time.sleep(3*(k+1)); err=str(e)
    return i,{'error':err}
out={}
with cf.ThreadPoolExecutor(4) as ex:
    for n,(i,r) in enumerate(ex.map(get,ids)):
        out[i]=r
        if n%250==0: print(n,flush=True)
json.dump(out,open(sys.argv[1],'w'))
print('done',len(out),'errors',sum(1 for r in out.values() if r and 'error' in r),'missing',sum(1 for r in out.values() if r is None))
