"""Pilot: extract per-site sampling design from papers with a local LLM, then
verify every quote verbatim against the paper text and every number against
its quote.  Nothing the model says is kept unless the text backs it.

usage: python -I extract_sampling.py TEXTDIR OUT.json [MODEL]
"""
import json, re, sys, time, urllib.request

TEXT, OUT = sys.argv[1], sys.argv[2]
MODEL = sys.argv[3] if len(sys.argv) > 3 else "llama3.3:70b"

# paper text file -> collections it is cited by: (code, site name, species, n series in ITRDB file, sample IDs)
PILOT = {
    "fran042": [("fran042", "Eyne", "Pinus uncinata")],
    "swit383": [("swit383", "Sihlwald-Albisboden", "Picea abies")],
    "esp090": [("esp090", "Vall de Cabanes, Pyrenees", "Pinus uncinata"),
               ("esp101", "Cazorla, Jaen", "Pinus nigra")],
    "deu493": [("deu493", "Serrahn", "Fagus sylvatica"),
               ("deu494", "Kellerwald", "Fagus sylvatica")],
    "alb003": [("alb001", "Thethi", "Pinus heldreichii"),
               ("alb002", "Fushe Lura", "Pinus heldreichii"),
               ("alb003", "Cuka Partisan", "Pinus heldreichii")],
    "tur091": [("tur091", "Lesser Caucasus (DTH)", "Pinus sylvestris")],
    "czec006": [("czec006", "Krkonose Mountains treeline", "Picea abies")],
    "nor031": [("nor031", "Mount Iskoras", "Pinus sylvestris"),
               ("nor032", "Mount Iskoras", "Juniperus communis")],
}

PROMPT = """You are extracting the field sampling design from a tree-ring paper.

Sites of interest (the paper may name them differently, or not discuss some at all):
{sites}

For EACH site of interest, report only what the paper states explicitly:
- n_trees: number of trees (or timbers/logs) sampled or used, as an integer, or null
- n_series: number of cores, radii or measurement series, as an integer, or null
- cores_per_tree: how many cores/radii per tree, as stated (e.g. "2", "1-3"), or null
- id_scheme: any statement of how samples are labelled or coded, or null
- quotes: a list of sentences copied EXACTLY, character for character, from the
  paper text that state each value you report. Every non-null value must be
  supported by at least one quote. Do not paraphrase, do not merge sentences.
- found: true if the paper discusses this site at all, else false

If the paper gives only pooled numbers for several sites together, report them
under "pooled" instead, with quotes. Never compute or infer a number.

Answer with JSON only, in this shape:
{{"sites": [{{"code": "...", "found": true, "n_trees": null, "n_series": null,
  "cores_per_tree": null, "id_scheme": null, "quotes": []}}],
  "pooled": [{{"what": "...", "value": "...", "quotes": []}}]}}

PAPER TEXT:
{text}
"""


def norm(s):
    s = s.replace("­", "").replace("ﬁ", "fi").replace("ﬂ", "fl")
    s = re.sub(r"-\s*\n\s*", "", s)          # de-hyphenate line breaks
    s = re.sub(r"[‐-―−]", "-", s)
    s = re.sub(r"[‘’“”\"']", "'", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def ask(text, sites):
    body = json.dumps({
        "model": MODEL, "stream": False, "format": "json",
        "options": {"temperature": 0, "num_ctx": 32768},
        "prompt": PROMPT.format(sites=sites, text=text),
    }).encode()
    req = urllib.request.Request("http://localhost:11434/api/generate", body,
                                 {"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=3600))
    return r["response"], r.get("prompt_eval_count"), r.get("eval_count")


def verify(ans, ntext):
    """Mark each quote verbatim/not, and each number supported/not."""
    def check_quotes(qs):
        return [{"quote": q, "verbatim": norm(q) in ntext} for q in qs if isinstance(q, str)]
    for s in ans.get("sites", []):
        s["quotes"] = check_quotes(s.get("quotes", []))
        good = " ".join(norm(q["quote"]) for q in s["quotes"] if q["verbatim"])
        s["supported"] = {}
        for k in ("n_trees", "n_series", "cores_per_tree"):
            v = s.get(k)
            if v is None:
                continue
            words = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five"}
            sv = str(v).strip()
            s["supported"][k] = bool(re.search(rf"\b{re.escape(sv)}\b", good)) or (
                sv in words and re.search(rf"\b{words[sv]}\b", good) is not None)
    for p in ans.get("pooled", []):
        p["quotes"] = check_quotes(p.get("quotes", []))
    return ans


results = {}
for paper, sites in PILOT.items():
    raw = open(f"{TEXT}/{paper}.txt").read()
    text = re.sub(r"\[\[page \d+\]\]", "", raw)
    # Drop the reference list: it is long and cannot state a sampling design.
    m = re.search(r"\n\s*(References|REFERENCES|Literature cited|LITERATURE CITED)\s*\n", text)
    if m and m.start() > len(text) * 0.5:
        text = text[: m.start()]
    sites_s = "\n".join(f"- {c}: {n} ({sp})" for c, n, sp in sites)
    t0 = time.time()
    resp, pin, pout = ask(text, sites_s)
    try:
        ans = json.loads(resp)
    except json.JSONDecodeError:
        ans = {"unparsed": resp}
    if "unparsed" not in ans:
        ans = verify(ans, norm(raw))
    ans["_meta"] = {"model": MODEL, "seconds": round(time.time() - t0), "prompt_tokens": pin, "output_tokens": pout}
    results[paper] = ans
    print(paper, ans["_meta"], flush=True)
    json.dump(results, open(OUT, "w"), indent=1, ensure_ascii=False)
