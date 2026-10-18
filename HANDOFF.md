# EHD — European tree-ring archive visualizer

Interactive view of individual subfossil and historical tree logs on a shared
time axis: one rectangle per log, greedily packed into rows, coloured by taxon,
with hover tooltips and click-through to each log's measured ring-width curve.

**Status: M1 complete.** Full pipeline runs end to end, **73,390 logs** in the
local build (191 of them floating collections placed by their published
calendar anchor), parser cross-validates against dplR at 100%. **The live site
still shows the 2026-08-28 build (76,609)** — the 2026-10-18 rebuild is
committed but not deployed.

## Map view (2026-10-18, first attempt, not deployed)

Timeline / Map switch in the controls (`#map` in the URL restores it). One
circle per **distinct published coordinate** (1,463), area ∝ logs passing the
taxon + era filters, pie by taxon, largest drawn first. Hover for a tooltip;
click for a panel listing the point's collections; "Show on timeline" (or a
row) restricts the timeline to them, with a "Place: …" chip to clear it. The
map ignores the place filter so every place stays clickable. Choices Howard
made up front: exact-coordinate clusters, self-hosted outlines (no tiles),
linked view, pies.

- Base layer: `python -m ehd.basemap` → `web/data/basemap.json` (438 KB,
  lazy-loaded on first map view). Natural Earth 1:50m v5.1.2, each file
  SHA-256 pinned; cached under `<data root>/raw/naturalearth/`. **Must be run
  before deploying** — emit does not build it. The clip box is far wider than
  the corpus because a lon/lat cut shows as a false coastline (it did, at
  32 W–62 E); zoom-out is floored at 0.75 × fit-all-points for the same reason.
- Projection: spherical LAEA centred 52 N 10 E (the EPSG:3035 centre).
  Verified numerically: Jacobian = R² cos φ to 1e-7 over 30–75 N, 30 W–60 E.
- Invariant in `applyFilters`: logs in circles + unmapped = logs passing the
  filters, else `console.error`. 3 collections (86 logs: GERM013,
  GERM14_CORRECTED, GERM301_CORRECTED) have no coordinates; noted on the map.
- Verified in Chrome: counts vs an independent recount (Regensburg pre-1500 =
  43), panel refresh/close on filter change, timeline hand-off (490 logs, 42
  sites, packing check passes), chip clear, no console errors, both themes.
- Wheel zoom: confirmed by Howard with a real wheel in Firefox. The Chrome
  extension's scroll sends no wheel events, so the automated check used
  dispatched WheelEvents (anchor drift < 1 px). Those reported a wrong
  `offsetX`, so the map's wheel uses `clientX − rect`; the timeline's wheel
  still uses `offsetX`, with no real-user problem seen.
- Known limits / next ideas: circles overlap heavily in the Alps at fit zoom
  (size slider helps); 821 collections publish only 2 decimals, so one place
  can be several neighbouring circles; no touch or keyboard support (the
  timeline has none either); place names are "largest collection + N more"
  (a shared-word heuristic was tried and produced "Valley, Cyprus").

Before deploying: run `ehd.basemap`, recapture `og.jpg` (see Link previews),
and run `scripts/verify_deploy.py` (now also checks `/data/basemap.json`).

## Rebuild of 2026-10-18 (committed, not deployed)

`fetch --templates --refresh`, `harvest`, `emit`, `validate`, `sweep` all run.
pytest 139 passed.

- **Withdrawn studies withheld** (`corpus.KNOWN_WITHDRAWN`, `harvest.withdrawal()`):
  harvest found exactly the predicted 25 studies / 34 files; emit withholds
  **3,424 logs**. The live→new site diff is exactly those 25 sites plus 5 new.
- **Taxon from the template's Latin name** (AUST115 oak→pine etc., see git log).
- **Archive changes since 08-28**, separated from the withdrawal effect:
  76,609 − 3,424 = 73,185; new sites esp102 (31), esp103 (39), pol301–303
  (15/14/30) = +129; germ4 lost series `048052` = −1; esp104/105 +77 (below)
  → **73,390**. Ring values edited inside existing series in fran009, germ4,
  grc034, roma009. Span now 12429 BC – **2025 CE**. Listing: 5,638 `.rwl`,
  3,092 templates (+15 each). `fetch` prints only the first 20 changed names.
- **Study records no longer list the legacy `-noaa.rwl` files** — 2,402 of
  harvest's 2,407 "record no longer lists file". Harmless (always deduped as
  re-encodings). The other 5: fra053–055, pola021 (known), tur091x.
- **New reviewed table `corpus.REVIEWED_SPAN_DEFECTS`** (Howard chose this,
  "option B", 2026-10-18; revisit if a cleaner approach appears). esp103–105
  (Canfranc, Olano) all declare `Last_Year 1928`, data runs to 2025; for
  esp104/105 that makes the pair descend, which `declares_years_bp` reads as
  BP, withholding 77 living trees as floating. The sweep's self-check caught
  it. Rejected alternative: tighten the BP rule ("descending and future as
  CE") — it would let a BP file mislabelled CE plot at its ordinals, the
  dangerous direction. Entries pin the exact raw pair; `SpanDefectStale` fails
  the build once NCEI corrects it. The sweep reports the raw pair, not its BP
  conversion.
- **Sweep vs NCEI progress**: 2,032 of 2,068 files exact (was 1,887);
  **12 reportable** (was 152), including esp103–105.

**For the next NCEI mail** (plain text, see the sweep entry under Next):
esp103–105 spans; che419–423 publication DOIs are consecutive unrelated
Dendrochronologia articles (Stradivari harp, Patagonian *Nothofagus*, …) —
only che417's is Hartl's paper, **and the viewer links those collections to
the wrong papers**; esp090's DOI is the Cazorla black-pine paper (esp101's),
which cites the Pyrenees site only as a reference; tur091x.rwl is
byte-identical to tur091t.rwl and the record lists only `t`; plus the earlier
items under "Open audit findings".

## Same-tree merging — feasibility (2026-10-18), not started

Goal: show one rectangle per physical tree/timber, with all its series in the
detail view. **No archive field records tree membership** — the template's
`Tree ID:` just repeats the series ID, and ~0 of 3,092 templates document an ID
scheme. Three cases:

1. *Byte-identical copies* across collections — 2,014 redundant logs, 60 pairs
   (`scripts/audit/duplicate_sweep.py`). Certain. Open decision: which copy is
   canonical (Howard, deferred).
2. *Several cores/radii of one tree* — inferable from IDs, checkable by
   correlation. `scripts/trees/tree_feasibility.py` (first-difference log
   widths, ≥30 yr overlap, on the old 76,609 payload): ID-sibling pairs r
   q05/50/95 = 0.39/0.68/0.88 vs between-group 0.14/0.42/0.68; ~1,100 of
   ~1,110 testable collections separate by ≥0.1 in median. **Verifies a scheme
   per collection, not a pair**: a series' best match is its sibling only
   65.7%. ~24,000 series (31%) have opaque IDs (`LUB001`, `nr12`). The
   six-digit SSSTTC rule must be guarded (`czec005` `000001…` are trees).
3. *Variable files* (e/l/w/x) — already deduped (trap 6).

**Paper pilot** (`scripts/trees/extract_sampling.py`, `pdf2txt.py`; Llama 3.3
70B via ollama, ~4–7 min/paper): 8 open-access papers, 13 collections. 8 gave
a checkable count — alb003 77 trees/124 series and alb002 99/124 (paper's
Table 1; its text says 89) match the ID parse exactly; czec006 "one core from
each tree", 143 = 143; deu493 consistent; **deu494 exposed a parse error**
(`KEL21_A/_B`, underscore — ≤50 trees, parse says 79); nor031/032 consistent.
swit383 confirmed the scheme (E/S = east/south cores) but its count conflicts.
tur091, esp101, esp090, fran042 gave nothing usable. Best case (recent,
single-site, OA); only ~37% of series sit in a cited collection at all.
The LLM gave 16/19 verbatim quotes (one "..." splice, correctly rejected) and
reported cores *collected* (100) instead of series *crossdated* (86/79); a
plain regex found every sentence it did. Use it to locate passages, never to
supply numbers. Elsevier/Springer/MDPI block curl; OpenAlex repository copies
worked for most; Claude in Chrome is allowed with Howard's per-use approval at
human pace.

Proposed design when this resumes: a reviewed per-collection ID-scheme table
(like `anchors.py`) — merge only where a scheme is reviewed and passes the
correlation check; papers as one evidence source; everything else stays
"series, tree unknown". Merged span = union of cores.

## Open audit findings (2026-10-02 audit of the old payload)

`scripts/audit/` is committed as one-off scripts reading `web/data`; rerun
against the new build before acting on them (withdrawals removed some).

- **ITA blue-intensity files** — `ita07[234]b[el]{25,50,75,100}.rwl`, 24 files,
  608 logs, labelled "total ring width" in mm. `SITE_RE` does not match the
  suffix, so they are kept as separate sites. All redundant: same trees as
  `ita073`, `ita074`, `ital050`. Fix: treat `b[el]\d+` as a variant suffix.
- **Duplicate series across collections** — see case 1 above. Plus `nor032` ⊂
  `nor051` at exactly 10× scale and `bulg003x` on `bulg001`'s trees.
- **Upstream defects for NCEI**: AUST115 title; withdrawn files still served;
  ITA063 code; Romanian duplicate pairs disagree in longitude by ~0.6°;
  `fran5`/`fran8` and `germ020`/`swit102` share series across sites ~37 km and
  ~600 km apart; `ita060` `LARE003X` 1885 = 59.83 mm (typo); FRA053–055 study
  records now point at `miramont2025-DRM*.txt` instead of the `.rwl` — ask if
  superseded, since our anchors rest on those files; POLA021 lists no `.rwl`
  and has no note. The 2026-08-28 sweep's "no age range" row (2704/2710) was
  withdrawn studies — retract it. Plan: one plain-text email.
- **Viewer**: the 13 maximum-density collections get a "peak … mm" caption.
- **Definition**: a "log" is a measured series (core/radius), not a tree.
- **Map interface** (user feedback) — facts for it: one taxon per collection
  (pies only arise when collections are merged), 919 collections on 344 shared
  coordinates, 42 at one Regensburg point, half the coordinates at ≤2 decimals
  (counts from the old payload).

## The Hohenheim question

The project was conceived around the 12,460-year Hohenheim oak+pine chronology.
**Its per-log data has never been published.** Verified by direct probe, not
inference:

| Source | Result |
|---|---|
| ITRDB / NCEI | no Hohenheim study; only 14 measurement studies worldwide start before 3000 BC |
| Zenodo, PANGAEA | nothing relevant |
| DCCD | service down (2026-08-18: `dendro.dans.knaw.nl` resolves to 194.171.144.80 and completes a TLS handshake, then the request fails — the host is alive, so ask DANS whether the holdings survived) |
| Billamboz German Neolithic oak (GERM021–031) | averaged `.crn` chronologies only, no per-log data |
| Belfast Irish oak | in ITRDB only from 1531 CE |

The public record therefore has a hole where Hohenheim should be. Measured
from the built payload (2026-09-26): **no log is alive between 11746 BC and
5408 BC**, ~6,340 years. Before it, only the anchored French Late Glacial pines
(fra053–055, 12429–11746 BC); after it, continuous coverage from swed334
onward. The Swiss floating collections would not fill it even once anchored —
their declared ranges sit at ~13,050–10,800 BC. (This line used to say
"10,800 BC to 4,000 BC", which described study start dates, not log coverage.)
Decision (Howard, 2026-08-17): build the prototype on public ITRDB
data and pursue Hohenheim separately. The pipeline is source-agnostic, so a new
per-log corpus drops in as another input.

## Running it

```bash
uv venv --python 3.12 && uv pip install pytest brotli   # once
python -m ehd.fetch --templates  # corpus + NOAA templates (~8,700 files)
python -m ehd.fetch --refresh    # re-download only what the archive has changed
python -m ehd.harvest    # study metadata + corpus reconciliation report
python -m ehd.emit       # build web/data payloads
python -m ehd.validate   # cross-check parser against dplR + invariants
python -m ehd.sweep --csv docs/out.csv   # study records that disagree with data
python scripts/serve.py                              # then open localhost:8777
```

`scripts/make_favicon.py` regenerates `web/favicon.{ico,svg}` from the
palette in `style.css`; it is not part of the pipeline and only needs rerunning
if the palette changes. It needs `ffmpeg` (already installed) to pack the ICO,
and writes its intermediate PNG with stdlib `zlib` because the venv has no
image library. That PNG goes to a temp dir, not `web/`, which is the deploy
directory.

Use `scripts/serve.py`, not `python -m http.server`: `ehd.emit` writes
`logs.bin` and `index.json` brotli-compressed under their plain names, and
`web/_headers` is what declares that to the browser. The dev server reads the
same `_headers` file, so local behaviour matches the deployed site; a plain
static server serves the compressed bytes undeclared and the viewer draws
nothing.

Deploy (static, Cloudflare Pages project `ehd`):

```bash
npx wrangler@4.124.0 pages deploy web/ --project-name ehd --branch main
```

`wrangler` is not installed and not on PATH; it runs via `npx`. The OAuth token
holds only `account:read`, `user:read`, `pages:write` and is stored encrypted with
the key in the macOS Keychain (`wrangler login --use-keyring`). `web/_headers`
carries the cache policy — read the comment in it before lengthening any max-age.

Data root resolves to `$EHD_DATA`, else `/Volumes/Expansion/EHD`, else `./data`.
Note the external drive's *root* is `root:wheel` and not writable by `howard`;
`/Volumes/Expansion/EHD` had to be created once with sudo.

`python -m ehd.validate` needs R with dplR (`install.packages("dplR")`).

## What the numbers are

**Current build (2026-10-18):** 5,638 `.rwl` listed + 3,092 templates → 2,068
files after dedup → **76,950 logs**: 76,460 absolute + 191 anchored + 77
disputed (esp104/105, reviewed) + 86 unverified + 136 floating; 3,424 withheld
as withdrawn; **73,390 plotted**, 59,448 packed rows. dplR agreement 100.0000%
on 65,438 series. The detail below is the 2026-08-28 build and is kept for its
reasoning; its counts are superseded.

All figures below are from the harvest and rebuild of **2026-08-28**.

- 5,623 `.rwl` files listed in ITRDB `measurements/europe/`, plus 3,077
  maintained NOAA templates (`*-rwl-noaa.txt`)
- → 2,061 files after dedup, → **76,745 logs**, 76,609 plotted
- 327 logs are floating. **191 are plotted via a reviewed calendar anchor**
  (fra053–055, brit099/100 — see `ehd/anchors.py`, added 2026-09-26); **136
  remain withheld** (the Swiss Late Glacial swit195–198, swit240); **0 disputed** — NCEI corrected neth005 and brit, so the class is
  now empty; 86 dated but unverifiable against metadata (was 3,464, and that
  collapse is the measure of what the frozen templates were costing)
- Span 12429 BC – 2023 CE (fra053 ring 1 = 14378 cal BP); 2,056 sites. The
  oldest *calendar-dated* collection is still swed334 at year −5407, which is
  **5408 BC**, not 5407 BC as this file used to say — see trap 10.

## Format traps, all found in real files

Each of these silently corrupts the result if mishandled; each has a regression
test in `tests/`.

1. **RWL is fixed-width.** IDs run straight into the year (`0003401Q1890`). A
   whitespace parser fails on ~32% of the corpus.
2. **BC years borrow column 8** for the minus sign (`C002   -2894`).
3. **`-999` is a missing ring, not a terminator.** It appears mid-series in long
   runs; treating it as a terminator cut one che419 log from 1854–2010 to
   1854–1864.
4. **The terminator is per-file.** In a 0.001 mm file (`-9999` terminator), `999`
   is a real 0.999 mm ring. A stray `-9999` in an otherwise 0.01 mm file
   (finl084) flips the detection, so terminators are trimmed from series *ends*
   rather than acted on inline.
5. **Trailing locally-absent rings** (negative flags such as `-8`) must not
   extend a span; dplR agrees. Interior ones are real zero-width rings.
6. **Three kinds of duplicate**: `-noaa.rwl` re-encodings (2,411), per-variable
   suffixes measured on the same trees (`brit048e/l/n/w/x`, 1,151 files), and
   series IDs that repeat across sites. Left alone these inflate the log count
   by ~36%.
7. **NCEI's `Continent>Europe` filter is unusable.** As of 2026-08-28 it returns
   9,022 records, 6,834 of which reference a `.rwl`, of which only 2,195 have
   coordinates inside Europe. It also omits genuine European studies — SWIT240,
   and FRA053–055, which is part of why those three went unnoticed for so long.
   The `measurements/europe/` directory listing defines the corpus instead, and
   `ehd.sweep` resolves what the filter hides by looking studies up by id.
8. **There are two NOAA template families and only one is maintained.** NCEI
   renamed the per-study template from `<site>-noaa.rwl` to
   `<site>-rwl-noaa.txt` in February 2023 and changed the field vocabulary with
   it: `Earliest_Year`/`Most_Recent_Year` → `First_Year`/`Last_Year`,
   `Elevation` → `Elevation_m`, `Online_Resource` → `NOAA_Landing_Page`. Both
   families are still served, side by side in the listing, with nothing marking
   the older one as superseded — and the old one is frozen: **nothing in it is
   dated after 2023-01**, while the new one runs to 2026-08. Ed Gille's August
   2026 corrections went only to the `.txt` files.

   Reading the wrong family fails silently in the worst way. The old names give
   a three-year-old snapshot; the old *field names* against a new file give an
   empty header, and an empty declared span reads downstream as "nothing to
   check against" rather than as an error. That is how fra053–055 — 111 French
   Late Glacial pine logs whose year column is ring ordinals — were plotted at
   years 1–434 CE for the life of the project. They have no `-noaa.rwl` sibling
   and no study record the continent filter returns, so nothing declared a span
   for them and the dating classifier had nothing to catch. `corpus.py`'s
   `read_template_header` now reads the maintained family first and keeps the
   old one only as a fallback for the 13 site codes that exist under no other
   name. `tests/test_templates.py` pins both vocabularies.

   `Time_Unit` is present in the new template and is *not* usable on its own:
   brit099 and brit100 declare 5224→4813 under `Time_Unit: CE`. The eight Late
   Glacial collections do say BP (`cal yr BP`, or `calendar year before present`
   for fra053–055). An earlier version of this note said they left it empty; that
   was false when written — the files fetched that morning already carried it.
   Ordering remains the mechanism because brit099/100's field is wrong.

   **BP, not BC — verified, not inferred from the ordering.** The question came
   up because "counts backwards" is equally true of BC, so the ordering test
   alone does not establish which convention is meant. Two independent sources
   do. The depositors state it in the file: brit099's `Description` reads *"the
   TRW series are in index years and have to be converted to cal. years BP with
   the earliest year being 5224 ±4 cal. years BP"*, brit100 the same with 4612.
   And NCEI applies the conversion itself for eight of the ten — `earliestYearCE`
   is exactly `1950 - First_Year` for swit195–198, swit240 and fra053–055. The
   two it skips are brit099 and brit100, whose `earliestYearCE` reads 5224 and
   4612, dates in the future; they should be −3274 and −2662. That is now a
   reported item in the sweep draft, and it is a *units* fix, not a licence to
   replace those spans with the files' ring ordinals.

9. **A declared span that disagrees with the data is an archive defect, but
   overlap is still the right test.** The first classifier demanded endpoint
   agreement and so called 2,682 logs floating when only 216 are.

   The original reasoning here was wrong and is corrected: it claimed a
   narrower declared span was *normal*, describing the site chronology rather
   than the longest log, with fran10 (declared 1943–1975, measured 1747–1988)
   as the worked example. NCEI say the opposite — the study range is meant to
   match the `.rwl` file's range — and they changed fran10 to 1747–1988 on
   2026-08-21 when asked. The corpus agrees with them: **1,871 of the 2,029
   deduplicated files with a study-record span match it exactly (92.2%)**, and
   narrower-than-data occurs in 70 files, not routinely.

   Overlap remains correct as a *classifier*, because it is robust to metadata
   being wrong in either direction, which it demonstrably is. What changed is
   the justification, not the test. See `tests/test_dating.py`.

10. **Years are astronomical: year 0 exists and is 1 BC.** Verified in the raw
    data, not assumed: neth009's `NWH011` has a `-10` decade line holding
    −10…−1 followed by a `0` line holding year 0, and 80 logs across seven
    collections have a ring in year 0. The viewer printed −y as "y BC" until
    2026-09-26, so **every BC label on the site was one year late** and year 0
    read "0 CE". `fmtYear` now prints 1−y; axis ticks step through historical
    numbering (`tickYear`) so labels stay round. `tests/test_year_labels.py`
    runs the shipped functions under node. BP converts as `1950 − BP` straight
    into this convention (1950 BP = year 0 = 1 BC).

11. **Ring-width units are per file and must reach the viewer.** 206 files
    (6,171 logs) measure in 0.001 mm; the parser always knew (`precision_mm`),
    but the value shards did not carry it and the viewer divided every value by
    100, so the detail panel's "peak" read 10× too wide for all of them until
    2026-09-26 (brit100 showed a 18.94 mm yew ring; it is 1.89). Shards now
    carry `"u"` (mm per unit) and `emit` refuses any unit other than 0.01/0.001.

## Verification

- `pytest tests/` — 111 tests (2026-09-26); `test_anchors.py` pins each
  calendar anchor at both ends and that the Swiss umbrella spans are refused; parser fixtures are the files that broke earlier
  parsers; `test_dating.py` pins every real collection the classifier must
  separate into absolute / floating / disputed; `test_templates.py` pins the two
  template vocabularies; `test_listing.py` pins the staleness check;
  `test_sweep.py` pins the two ways the NCEI report can produce a wrong row.
- `python -m ehd.validate` — **100.0000% span agreement with dplR on 65,154
  series**, 0 disagreements, 0 invariant failures, 0 series found by dplR that
  we miss (we additionally read 11,591 series dplR cannot). Re-run 2026-09-26
  after anchoring; unchanged. Anchored logs are compared in the file's own
  numbering (`Log.year_shift` is subtracted), since dplR knows nothing of the
  anchor. Dating classes: 76,332 absolute + 191 anchored + 86 unverified + 136
  floating = 76,745.
- `python -m ehd.sweep` self-checks that the ten floating collections are
  quarantined and the four corrected studies read exact, and that its own
  partition accounts for every file. It exits non-zero if not.
- `ehd.emit` asserts the packing is overlap-free before writing.
- Palette validated with the dataviz skill's checker in both light and dark.

## Hosting

Live at **https://treerings.howardalandman.org** (Cloudflare Pages project `ehd`,
also reachable at `ehd-612.pages.dev` — the bare `ehd` pages.dev name was taken).

Source: **https://github.com/HowardALandman/TreeRings** (public, MIT). Push with
the default `github.com` SSH host, which maps to the `HowardALandman` account;
the `HAL-BFF` key is scoped to the `github-bff` alias and used only by
`~/src/BFF/cubff`. Note this repo's branch is `main`, renamed from `master`
when it was first pushed.

Domain `howardalandman.org` registered 2026-08-19 at Cloudflare Registrar, 1-year
term, auto-renew on, expires 2027-08-19. Cloudflare is both registrar and
authoritative DNS, so `treerings` is a CNAME it manages itself and Universal SSL
already covered `*.howardalandman.org`. The apex is deliberately unrouted, reserved
for an umbrella landing page; further projects go on their own subdomains rather
than subpaths, so each keeps an independent deploy and file budget.

Verify a deploy with `python scripts/verify_deploy.py`, which checks every
served path, the http→https redirect, the security headers, the payload byte
counts, the link-preview tags, and the custom-domain/pages.dev parity described
below. Run it after every deploy; it exits non-zero on any failure.

**Do not check status codes.** The recipe this script replaced was a handful of
curl lines checking `%{http_code}`, and on 2026-08-20 it reported all 7 fetch
paths passing on a deploy that had no `favicon.ico` at all. Cloudflare Pages
answers *any* unknown path with **200 and the body of `index.html`**:

```
$ curl -sI https://treerings.howardalandman.org/nonexistent-xyz
HTTP/2 200
content-type: text/html; charset=utf-8
```

So a 200 says nothing about whether the file was deployed. Every check in the
script instead fingerprints that fallback body and requires the response to
differ from it, and asserts an expected content type. The run opens by fetching
two paths that cannot exist and requiring them to be identical — if the
fallback is ever unstable, "is a real file" is meaningless and the whole run is
worthless. `/` is the one path that legitimately *is* `index.html`, so it is
compared against the local build instead, which also catches a stale deploy.

Two things this found on first run, on 2026-08-20's supposedly verified deploy:
`favicon.ico` was missing (200, `text/html`), and so was any link-preview tag.

**The zone injects a third-party script into the HTML.** Comparing `/` against
the build turned up 359 bytes the site does not serve:

```html
<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js/…"
        data-cf-beacon='{"version":"2024.11.0","token":"…"}' …></script>
```

That is Cloudflare Web Analytics, switched on at the zone, injected on the
custom domain only — `ehd-612.pages.dev` serves the file unmodified. It is
cookieless and Cloudflare's own, so it is not a leak, but it does mean the page
is not the dependency-free static site the rest of this document describes, and
it went unnoticed by a post-deploy check that included "browser console clean".
Turn it off under the zone's Analytics → Web Analytics if that is not wanted.
The check does not skip the comparison for it: `ZONE_INJECTIONS` in the script
names the beacon and strips exactly it, so any *other* injected content still
fails, and a beacon that stops appearing shows up in the run's output.

**The edge cache serves the previous deploy for a while.** The first check after
deploying showed the *old* `logs.bin` — 1,836,696 B, no `Content-Encoding`,
`cf-cache-status: HIT`. Nothing was wrong: the object was still cached from the
deploy before. A request with a cache-busting query string pulled the new one
and the cached entry refreshed. When verifying a deploy, append `?cb=$RANDOM` or
check the deployment-specific `<hash>.ehd-612.pages.dev` URL, or you will
measure the thing you just replaced and believe the deploy failed.

**`no-cache` did not survive on the custom domain — found and fixed 2026-08-20.**
`web/_headers` sets `no-cache` on `/data/*`, `/app.js` and `/style.css`, and that
is what `ehd-612.pages.dev` and the deployment URLs returned. On
`treerings.howardalandman.org` it came back as `max-age=14400` instead.

The mechanism was the zone's **Browser Cache TTL**, sitting on Cloudflare's
4-hour default (14400 s exactly). Per Cloudflare's docs it "overrides any
Cache-Control or Expires headers" whose value "is less than the Browser Cache
TTL setting" -- and `no-cache` is less than four hours, so every asset the edge
considered cacheable got rewritten. Confirmed rather than inferred: the rewrite
happened even on `cf-cache-status: MISS`, and the same asset fetched from
`ehd-612.pages.dev`, with no zone in front, still said `no-cache`.

What escaped it was what the edge does not cache at all -- `.json` and HTML come
back `DYNAMIC` and keep their headers; the cacheable extensions did not:

| | Cache-Control served (before the fix) | cf-cache-status |
|---|---|---|
| `logs.bin`, `app.js`, `style.css`, `favicon.ico` | `max-age=14400` | REVALIDATED |
| `index.json`, `values/*.json`, `/` | `no-cache` | DYNAMIC |

So the cache policy the `_headers` comment describes was only half in force, and
the missing half was the half it was written for. A pipeline rerun could leave a
visitor with a fresh `index.json` and a 4-hour-stale `logs.bin` -- mismatched
halves of one dataset, which would have drawn silently wrong rectangles.
`app.js`'s byte-length check would now turn that into a visible error, but the
error is the symptom; the setting below is the fix.

**The fix, applied by Howard 2026-08-20:** Cloudflare dashboard → the
`howardalandman.org` zone → Caching → Configuration → Browser Cache TTL →
**Respect Existing Headers**. It needs zone access the deploy token does not
have (`account:read`, `user:read`, `pages:write`; not even `zone:read`), so it
cannot be scripted from here. The docs are explicit that this is the off
switch: "Cloudflare does not override or insert Cache-Control headers if you set
Browser Cache TTL to Respect Existing Headers." It is
zone-wide, which suits a zone whose subdomains are independent deploys -- each
project's own `_headers` then governs its own caching. A Cache Rule scoped to
`treerings.howardalandman.org/*` is the surgical alternative if a future project
on this zone ever wants the 4-hour default back.

Verified after the change: all seven fetch paths now return byte-identical
`Cache-Control` from the custom domain and from `ehd-612.pages.dev` --
`no-cache` on `/data/*`, `/app.js`, `/style.css`, and Pages' own
`public, max-age=0, must-revalidate` on `/` and `/favicon.ico`. Edge caching
survives the change (`cf-cache-status: REVALIDATED`), so the CDN still serves
the bytes and only the browser-facing header changed. Compression and
negotiation are unaffected: `logs.bin` still 413,182 B br decoding to 1,836,696,
still 1,836,696 raw for a gzip-only client.

Re-verify with a cache-busting query if this is ever revisited, or the edge's
held objects answer for the old setting -- that is what made the first check
after the compression deploy look like a failure. `scripts/verify_deploy.py`
busts the cache on every request it makes, so this is handled as long as the
checking goes through the script.

The parity check against `ehd-612.pages.dev` is the one worth keeping, and is
now `verify_parity()` in that script rather than a note here: the Pages origin
shows what `_headers` actually declares, so any future divergence between the
two hostnames is a zone setting interfering again.

Two alternatives were considered and rejected:

- **Mark the payloads `private` or `no-store`** so the edge stops caching them
  and the override stops applying -- which is exactly why the `.json` files
  escaped. It would work from `_headers` alone, with no dashboard access, but it
  buys a correct header by giving up edge caching on the largest asset on the
  site. Wrong trade.
- **Content-hashed payload paths plus `immutable`**, which the `_headers`
  comment already proposes. Better end state, and it makes any cache
  misconfiguration harmless by construction rather than by policy -- but it does
  not by itself fix what is broken here, since `app.js` and `style.css` are
  overridden too and a stale `app.js` against fresh data is its own hazard.
  Worth doing when the extra revalidation round-trip starts to matter. Not a
  substitute for the setting above.

This was independent of the compression work -- it predated it and applied to
`app.js` and `style.css` equally. It went uncaught because the original
post-deploy check did not compare the custom domain against pages.dev.

## Link previews

Sharing the URL on Facebook produced a bare link with no graphic, because the
served HTML had no Open Graph tags and the site had no image file. Neither half
works alone — a tag pointing at an undeployed file gives the same blank card as
no tag at all — so `tests/test_link_preview.py` pins them together offline and
`scripts/verify_deploy.py` re-checks them against the live site.

The reason none of this can be done in `app.js`: crawlers do not run JavaScript,
so the visualisation, which exists only as pixels drawn into a `<canvas>`, is
invisible to them. Everything a shared link shows has to be static.

**The log count is hardcoded in three places in `index.html`** — the meta
description, `og:description` and `og:title` — plus the year span.
`tests/test_link_preview.py::test_hardcoded_log_count_matches_the_build` checks
them against the built `index.json`, so a rebuild that moves the count fails
the suite until the head is edited by hand. `og:title` is deliberately *not* the same string as
`og:site_name`; Facebook stacks the two and repeating the name prints it twice.

**`og.jpg` is now stale in two ways (2026-09-26):** its axis labels were drawn
by the old off-by-one `fmtYear` (one reads "0 CE"), and it predates the Late
Glacial and Fenland logs. Recapture it; `og:image:alt` describes the old image
and should be rewritten with it.

`web/og.jpg` is **a hand-captured screenshot, not a build artifact** — 1200×630,
the "Packed together / Before 1 CE" ladder, cropped from a 1316×906 browser
capture and scaled with `ffmpeg`. It is committed because nothing regenerates
it, and it will drift from the data as the corpus changes. To recapture: open
the site, set Layout "Packed together" and Era "Before 1 CE", screenshot the
viewport, then

```bash
ffmpeg -i shot.jpg -vf "crop=1316:691:0:0,scale=1200:630:flags=lanczos" -q:v 3 web/og.jpg
```

The 691 is whatever height gives 1.91:1 at the capture's width; the crop is from
the top so the title, taxon legend and time axis stay in frame. Rendering this
in the pipeline instead was considered and deferred — it would need the taxon
palette duplicated from `app.js` into Python, which is a second source of truth
for the one thing HANDOFF says not to change without re-running the validator.

**Facebook caches its verdict per URL.** After any change here, put the URL
through `developers.facebook.com/tools/debug/` and press *Scrape Again*, or the
old empty card persists no matter what the site now serves.

**Do not trust the Sharing Debugger. Paste the link into a post composer.**
Verified working 2026-08-26 — the card renders with the ladder image. Getting
there cost a long detour chasing diagnostics that were all wrong:

| What the tool said | What was true |
|---|---|
| 403 "Bad Response Code" on the `http://` URL | http returns a clean single-hop 301 to https |
| "og:image should be explicitly provided" | `og:image` is present, and found by a standards HTML parser |
| echo: "An error occurred while fetching content" | failed identically for `ehd-612.pages.dev`, which has no zone in front of it |

The echo failure on *both* hosts is what broke the case open: those two share no
security configuration, so a fault common to both is a fault in the tool. Meta's
crawler was never blocked — Bot Fight Mode and AI-crawler blocking were both
already off on the zone. The 403 has no explanation and did not need one.

The lesson worth keeping: this instrument reports failures for a site that is
provably fine, so establish a control before believing it (point echo at
`example.com`) and treat the composer as ground truth. Checking from this end —
status, content type, parsed tags, image dimensions, DNS, TLS, IPv6 — proved
everything except the one thing that mattered, because every one of those
requests came from here rather than from Meta's network.

## Payload compression

`ehd.emit` writes `logs.bin` and `index.json` brotli-compressed at quality 11
under their plain names; `web/_headers` declares `Content-Encoding: br` on those
two paths. The `values/` shards stay uncompressed for Cloudflare to handle.

Measured live, 2026-08-20, before and after the change, over the same five
first-paint requests with `Accept-Encoding: br, gzip, deflate`:

| | before | after |
|---|---:|---:|
| `logs.bin` | 1,836,696 | 413,182 |
| `index.json` | 345,660 | 254,711 |
| `/`, `app.js`, `style.css` | 10,113 | 10,841 |
| **first load** | **2,192,469 (2.09 MiB)** | **678,734 (0.65 MiB)** |

69% smaller, on the live custom domain. `logs.bin` was 84% of first load and
Cloudflare never touched it: the edge's auto-compression works from a
content-type allowlist that excludes `application/octet-stream`. `index.json` *was* compressed, but the edge's
on-the-fly brotli is tuned for speed rather than ratio (345,660 B against
254,711 B for `brotli -q 11`), so pre-compressing it wins another 91 KB.

Two things about this were expected to be problems and are not:

- **Content negotiation still works.** The worry was that pre-compressing forces
  brotli on every client. It does not: measured live, a request with
  `Accept-Encoding: gzip` gets `index.json` re-encoded as gzip (336,872 B) and
  `logs.bin` decompressed to its raw 1,836,696 B, and a request with no
  `Accept-Encoding` gets both raw. Cloudflare decodes and re-encodes at the edge.
- **`application/json` is on the auto-compress allowlist**, so pre-compressing
  `index.json` risked being re-encoded on top of itself. It is not — the br bytes
  pass through byte-identical to what `emit` wrote.

`DecompressionStream('brotli')` is **not** an option for a client-side decode
path: unsupported in Chrome as of 2026-08 (Firefox 147, Safari 18.4 only). Any
explicit-decode design would be stuck at the gzip tier, ~621 KB for `logs.bin`.

The compression and the `_headers` rule are two halves of one thing and break
the site if separated, so `tests/test_headers.py` pins them together and
`app.js` checks `logs.bin`'s byte length against `n_logs` and reports the likely
cause on screen if it ever mismatches.

## Shape of the data (drives the UI)

The archive is overwhelmingly modern: 7 logs alive in 5000 BC, 84 at 1 CE,
**62,199 in 1971**. Packed, that is a ~62,000-row wedge, so the viewer zooms on
both axes and offers era filters. The "Before 1 CE" + "Packed together" view is
the classic overlapping-chronology ladder and the most legible entry point.

## Next

- **Floating chronologies — 191 of 327 placed 2026-09-26; 136 Swiss remain.**
  `ehd/anchors.py` is a reviewed table, not a rule: a site gets a calendar
  position only if a person has read the evidence, and the build *fails* unless
  the file still reproduces the declared BP span at both ends.

  | Site | Logs | Anchor | Evidence |
  |---|---:|---|---|
  | fra053/054/055 | 111 | ordinal 1 = `First_Year` BP, ±2.5 yr | full span = declared length exactly (434/348/233) |
  | brit099 | 32 | ordinal 841 = 5224 BP, ±4 | replicated (depth≥2) span = 412 = declared; full span 413 misses |
  | brit100 | 48 | ordinal 635 = 4612 BP, ±6 | replicated span = 418 = declared; full span 453 misses by 35 |

  The Fenland reading is **inferred**: the depositors say "earliest year", and
  the replicated-span reading is the one that reproduces both declared ends
  exactly in both files. The 1 (brit099) and 5 (brit100) unreplicated leading
  rings sit before the stated anchor. Either reading is inside the stated σ.

  **The Swiss files have no per-file anchor anywhere in the archive.** All four
  Daettnau files declare the same site-wide 14237–12750 BP; swit240 declares a
  rounded 15000–14000 BP for 1,382 ordinals; NCEI's
  `correlation-stats/swit196.txt` says only "Beginning year: 1". Both anchor
  bases are refused by `anchors.offset` and pinned so in `test_anchors.py`.

  Literature, as far as it got (2026-09-26):
  - swit240's 1,382-ring span matches exactly the "floating, 1382-ring pine
    chronology" of **Kromer et al. 2004, Radiocarbon 46(3)**, anchored by 14C
    wiggle-match to the Cariaco varve chronology. *Plausible* identification
    by length only; full text not reached (the Arizona repository is a
    JS-only DSpace page, Cambridge core-reader gave the abstract only). A 2004
    Cariaco anchor is in any case superseded by IntCal20.
  - Schaub, Kaiser et al. (Dendrochronologia 2005, "Extension of the Swiss
    Lateglacial tree-ring chronologies") describe Gaenziloo/Landikon floating
    sub-chronologies (GAEALLCH_A/D, GAEYD_A), wiggle-matched to Cariaco.
  - Reinig et al. 2020 (Radiocarbon 62(4), "Illuminating IntCal during the
    Younger Dryas") — 13 Zurich pines, 11,950–13,160 cal BP; the PDF did not
    extract. The current placements live in IntCal20's floating-sequence
    data; intchron.org and intcal.org did not yield it by URL guessing.

  What would settle it: IntCal20's per-sample records for the Swiss trees,
  with ring positions and series IDs matchable to the ITRDB `DAECHAL*` /
  swit240 IDs — or ask Frank Reinig (Mainz) / Ulf Büntgen (Cambridge) directly
  for the IntCal20 calendar position of each ITRDB file. Uncertainty will be
  decades, not years; the anchor table already carries σ for that.

- **App title is hardcoded to Europe.** `web/index.html` and `web/app.js` both
  say "European Tree-Ring Archive". Accurate today, wrong the moment a
  non-European corpus lands. Make it follow the corpus when the ITRDB region is
  parameterised (currently hardcoded in `ehd/config.py` `ITRDB_EUROPE` and
  `ehd/fetch.py` `list_europe_files`). The other seven ITRDB regional directories
  are `africa`, `asia`, `atlantic`, `australia`, `centralamerica`, `northamerica`,
  `southamerica`; everything downstream of the fetch is already region-agnostic.
- **Content-hashed payload paths.** `no-cache` costs a revalidation round-trip on
  every visit and depends on nothing upstream rewriting it -- which is exactly
  what the zone did until 2026-08-20. Hashing the payload filenames and serving
  them `immutable` would make staleness impossible by construction instead of by
  policy, and would be faster. Hash `app.js` and `style.css` too, or the same
  mismatch just moves there. Not worth it at current traffic; see the cache
  discussion under Hosting.
- **Taxon colour beyond 6 groups.** Only 3 hues can be distinguished at
  arbitrary adjacency; the by-taxon band layout is what makes 6 legal. Do not
  add hues without re-running the validator.
- **Metadata gaps.** 86 logs lack a declared span to check dating against, down
  from 3,464 before the template switch.
- **Metadata defects reported to `paleo@noaa.gov` — all accepted and fixed.**
  Sent 2026-08-19 (Howard edited the draft before sending); Ed Gille, NCEI
  Paleoclimatology Data Manager, replied 2026-08-21 and corrected all three.
  See `docs/ncei-metadata-report.md`. Verified live against the study API:

  | Study | Was | Now | Measured |
  |---|---|---|---|
  | BRIT101 (44081) | 271–276 | 271–726 | 271–726 |
  | NETH005 (3626) | −66–106 | 1834–2006 | 1834–2006 |
  | BRIT (4225) | 1750–1975 | 812–1458 | 812–1458 |
  | FRAN10 (2734) | 1943–1975 | 1747–1988 | 1747–1988 |

  He fixed more than the study records: the `-rwl-noaa.txt` templates now carry
  matching `First_Year`/`Last_Year`, and `brit.rwl`'s own header line 2 was
  rewritten from `1750 1975` to `812 1458`. FRAN10 was not in the report — he
  found and fixed it from the question the report asked, below.

  One residual, still true on 2026-08-28: `fran10.rwl` header line 2 still ends
  `1943   1988` while the record and template say 1747–1988. The end year was
  propagated into the file, the start year was not. Raised again in the sweep
  draft.

  `brit.rwl` is the one file in the corpus the archive has changed under us, and
  it is why `fetch --refresh` exists: the rewrite is the same byte length as
  what it replaced, so a size check sees nothing and only the directory
  listing's timestamp catches it.

  **He answered the definitional question, and the answer inverts trap #9:**
  "The time ranges for the ITRDB studies should match the range of dates in the
  rwl file." A declared span that disagrees with the data is a defect, not a
  site chronology. He then asked for more: "Please let us know if you find any
  other studies whose age ranges do not match the rwl file age ranges."

  **Consequence for the pipeline, now realised:** the `disputed` class is empty
  as of the 2026-08-28 harvest. Its 23 logs were exactly neth005 (9) + brit
  (14), both records are correct, and re-harvesting dropped the class to zero.
  `tests/test_dating.py`'s comments have been rewritten to describe those
  records in the past tense; the test inputs are kept, because the classifier
  still has to reach `disputed` for the next such defect rather than silently
  withholding it as floating.

- **The sweep Ed asked for — sent 2026-08-28 19:35; NCEI working through it.**
  `ehd/sweep.py`, with `docs/ncei-sweep-2026-08.txt` as the mail and `.csv` as
  its attachment. (This entry said "not yet sent" until 2026-09-26; the send
  was never recorded here.) Ed Gille acknowledged it, said he would start
  reviewing the European records from it, and that there is **no immediate
  need to run the report for other regions** - so the other seven ITRDB
  directories wait until he asks.

  **Progress, re-read live 2026-09-26:** 10 of the 154 CSV rows have changed,
  each now matching our measured span exactly, and they are **CSV rows 1-10 in
  order** (AUST003 ... TURK029) - he is working down the attachment. 142
  unchanged, 2 have no live span (studies 2710, 2704, as reported). BRIT099/100
  `earliestYearCE` still read 5224/4612 unconverted. To re-check, re-read each
  CSV row with `sweep.fetch_study_span(study_id)` and compare with its
  `declared_*` / `measured_*` columns. After a correction, `fetch --refresh`
  and a rebuild pick up any changed files and templates.

  **The draft is plain text on purpose, and the next one should be too.** It was
  first written in Markdown, which meant tables, `**bold**` and `---` rules that
  have to be reformatted by hand before anything can be sent — the format is for
  reading, not for mailing. `docs/ncei-metadata-report.md` had it right: plain
  text that happens to live in a file, pasteable as-is. Body wrapped at 78
  columns, pure ASCII, tables aligned with spaces. Send it from Gmail's
  **plain-text mode** (composer ⋮ → Plain text mode) so it goes out as
  `text/plain` and the recipient's client renders the tables in a monospace
  font; a rich-text paste puts them in a proportional font and the columns
  break. It is region-agnostic; pointing it at
  the other seven ITRDB directories needs only `config.ITRDB_EUROPE` changed.

  Result, against the fresh harvest: **138 studies / 152 files** whose study
  record disagrees with their `.rwl` data, out of 2,056 files with a record
  span. 1,887 match exactly (91.8%).

  ```
  1887  exact              152 reportable files, 138 studies
    77  declared narrower   40  off by exactly one year
    61  declared wider      39  off by 2-10
    21  declared offset     54  off by 11-100
    10  disjoint            19  off by >100
     5  no record span
  ```

  The 21-study fencepost pattern predicted from the stale snapshot is real and
  survived every correction below: correct start, end one year late, and
  **fourteen of the 21 are consecutive Polish study codes** (POLA005–POLA018).
  That is reported as one probable batch error rather than 21 findings.

  **The one-year offset was checked for being ours before it was reported**, because
  the direction is exactly what trap 5 would manufacture if the parser trimmed a
  trailing locally-absent ring: the record ends a year *later* than we measure.
  Three independent confirmations — dplR reads 20 of the 21 and agrees with our
  end year on all 20; `brit11.rwl`, which dplR cannot read, was checked by hand
  and against a throwaway scanner sharing none of `rwl.py`'s assumptions (no
  fixed-width fields, different terminator handling), which agreed exactly; and
  in each file several series reach the end year, so it is not one odd series.
  88% of all flagged files and 39 of the 40 off-by-one cases carry dplR
  validation. Redo this check before reporting a small-delta group again.

  Three things the first draft got wrong, all caught before anything was sent,
  and all now pinned by tests:

  1. **The do-not-touch list was hardcoded and already out of date.** It named
     the seven known floating collections; fra053–055 are three more, and the
     draft would have asked NCEI to overwrite their only calendar anchor with a
     ring count. Membership is now decided by `corpus.classify_dating` — the
     same classifier the viewer uses — and `KNOWN_FLOATING` is only an assertion
     that the known ones are still caught, with anything new flagged for
     confirmation by hand.
  2. **Seven rows were describing a sibling file.** A study owns several
     measurement files — earlywood, latewood, maximum density, measured on the
     same trees. NORW011 declares 1550–1997, which its `norw011.rwl` does not
     measure but its `norw011e.rwl` and `norw011l.rwl` do exactly. The
     comparison now checks the declared span against every file of the site and
     their union before calling anything a defect.
  3. **32 files looked recordless; 27 were not.** The `Continent>Europe` filter
     hides real studies, so "no record" was partly an artefact of the filter.
     `sweep.resolve_missing` recovers the study id from the file's own template
     header and looks it up directly. Three files resolve to nothing by any
     route (`germ013l`, `germ14_corrected`, `germ301_corrected`) and are
     excluded rather than counted as passing; two studies (2710, 2704) have a
     record with no age range at all, which is a different defect and is
     reported as one.

  Every row is re-read live by `NOAAStudyId` at report time, independently of
  the harvest snapshot, so nothing already fixed gets reported. Three rows
  (AUST003, GRC033, AUT130) were additionally confirmed by hand against the live
  record and a freshly downloaded file.

  Worth telling him, and in the draft: of the 152 flagged files, 123 have a
  readable span on `.rwl` header line 2 and **79 of those agree with the study
  record rather than with the data in their own file** — so correcting the
  record alone leaves most of these files still self-contradictory, and the
  record was probably derived faithfully from a header that was already wrong.
  The `-rwl-noaa.txt` template agrees with the record in all 152, so those two
  are one source and cannot check each other.

- **Hohenheim per-log data → CEZA Mannheim.** The Hohenheim AG dissolved
  2026-02-28; the collection (~3,000 boxes) is at the Curt-Engelhorn-Zentrum
  Archäometrie, which is entering existing ring-width measurements into a
  database. Contact Dr. Thorsten Westphal via the institute's general address,
  `info@ceza.de`. The institute rebranded from `cez-archaeometrie.de` to
  `ceza.de` (the old domain 301-redirects); both still share MX and A records,
  so older personal addresses on the old domain likely still route, but the
  general address is the one to use.
- Local LLMs are unused so far; the natural fit is tidying multi-language site
  and investigator strings for display.
