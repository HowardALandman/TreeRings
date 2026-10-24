# Survey of available per-series tree-ring data

Started 2026-10-24. Goal (Howard): gather whatever is available, even-handedly,
**not** aimed at a date range — targeting the 11746–5408 BC gap would bias the
corpus toward whatever happens to fill it.

## Inclusion criteria

A source is in scope if it publishes **per-series** measurements (one tree or
timber per series: ring widths, or at least first and last ring) that can be
downloaded without a personal agreement. Chronologies (averaged `.crn`) are out:
they carry no logs. Every period counts. Region is recorded, not filtered —
whether to go beyond Europe is an open decision (below).

For each source record: what it holds, how its holdings were **enumerated**
(not sampled), where that enumeration ends, the dating basis of its series
(calendar, cal BP, ¹⁴C BP, floating), and overlap with what we already have.

## Denominator: where to look, from independent horizons

| # | Source of candidates | Horizon | Status |
|---|---|---|---|
| 1 | ITRDB directory tree, **all** folders under `measurements/` | NCEI file server | done 2026-10-24, below |
| 2 | NCEI paleo study search API, tree-ring studies by location | NCEI metadata, independent of folder layout | done 2026-10-24, below |
| 3 | re3data.org registry: repositories tagged dendrochronology / tree rings | repository registry | done 2026-10-24: thin, see below |
| 4 | General data repositories: Zenodo, PANGAEA, Dryad, Figshare, DANS Data Stations | search by keyword | PANGAEA sized 2026-10-24 (below); Zenodo counted only; Dryad, Figshare, DANS not started |
| 5 | Literature inventories: Reinig et al. 2018 Late Glacial inventory, IntCal20 tree-ring data list, regional long-chronology reviews | published lists of chronologies, which name their data holders | not started |
| 6 | Named labs and national databases (DCCD, WSL, CEZA, Belfast, Innsbruck, Göttingen, Helsinki, …) | from 3 and 5, not from memory | not started |

Sources 1–2 can disagree with each other: the ITRDB folders are one view and the
study metadata another, and material outside `measurements/europe/` already
turned up below. Sources 5–6 cover what was never deposited anywhere.

## 1. ITRDB folder tree (2026-10-24)

`measurements/` holds eight regional folders plus `correlation-stats`,
`supplemental` and four per-study folders. Our fetch reads only `europe/`.

Measurement `.rwl` files per regional folder (excluding `-noaa` templates):

| folder | files |
|---|---:|
| europe | 3,227 (= our 2,068 used + 1,159 variants skipped, exact) |
| northamerica/usa | 3,260 |
| asia | 1,822 |
| northamerica/canada | 1,233 |
| southamerica | 300 |
| australia | 238 |
| northamerica/mexico | 183 |
| africa | 139 |
| centralamerica | 8 |
| atlantic | 1 |

Per-study folders, outside the regional tree:

- `miramont2025/` — DRM1–3, Drouzet River (Southern French Alps) Late Glacial
  *Pinus sylvestris*, NOAA template v4, cal BP, contributed 2025-12-05. **DRM1 is
  our FRA053**: all 26 series match by ID and exact span. DRM2/DRM3 presumably
  FRA054/055 — not checked. Files are Latin-1 with CRLF although the header
  says UTF-8.
- `miramont2025b/` — Barbiers River (Southern French Alps), 11 Late Glacial
  pine series, **new to us**. `Time_Unit: radiocarbon year before present`
  (13015–12592 ¹⁴C BP) with a floating "Aix_scale": not calendar years, so
  floating until a calendar placement is found (cf. the Swiss Late Glacial
  files).
- `vothrurup2026/` — 14 "mixed" files, Minnesota sites (North America). Not
  examined.
- `zhao2018/` — one `AppendixS1.zip`. Not examined.
- `supplemental/` — `ca749` tree metadata and `cana650–652-po` (Canada). Not
  examined.

**Mirrored 2026-10-24** with `python -m ehd.fetch --all`: 15 folders, 29,432
files (2.24 GB listed, 2.5 GB on disk) under `raw/itrdb/<folder>`; 20,702 new,
8,730 European already held. Checked against the listings afterwards: every
file present, every size equal to the listed size, no saved HTML error pages,
no `.part` leftovers.

## 2. NCEI study search (2026-10-24)

**The API ignores `locationName`** — the parameter `ehd/harvest.py` has always
sent. With it, `dataTypeId=18&locationName=Continent>Europe` returns the same
first record as no filter at all (an ENSO reconstruction) and 9,103 studies,
North American fire-scar sites included; FRA053's study is not among them. The
harvest still got every file's record through its per-file fallback lookup by
the study id in the template, so the payload is right, but the query never
did what it says. The working parameters are `locations=Continent>Europe` and
`minLat/maxLat/minLon/maxLon`.

Both working filters, paginated to the end: `locations` 2,423 studies, the
`EUROPE_BBOX` box 2,354; 2,110 in both, 313 and 244 in one only (the two
definitions differ at the edges: Russia, Turkey, Iceland, North Africa). Union
2,667. Every file those studies list, grouped by folder, outside the expected
ones (`measurements/europe`, `chronologies/`, `correlation-stats`,
`reconstructions/`, `isotope/`):

| folder | .rwl / data files | notes |
|---|---:|---|
| `measurements/asia` | 1,357 | 211 with site inside `EUROPE_BBOX` (European Russia west of 45°E: 150 `russ*`, 61 `rus3*`, 103 studies; no name clashes with `europe/`) and 173 more Russian between 45°E and 60°E (Volga, Komi, Urals). Many of the latter are Schweingruber density variants (`e/i/l/n/t/w/x`), which the pipeline skips anyway. |
| `measurements/africa` | 63 | all inside the box: Algeria 33, Morocco 18, Tunisia 12 — the box is a box, not Europe |
| `miramont2025`, `miramont2025b` | 6 + 2 | see section 1 |
| `supplemental/europe` | 2 | Belgium. Not examined. |
| `edwards2022` | 1 | Sweden. Not examined. |
| `northern-archives` | 40 | none inside the box. Not examined. |

**NCEI labels all of Russia "Europe"**, out to 169°E (`russ303` at 106°E is
`Continent>Europe>Eastern Europe>Russia`), so the label cannot define scope.

**`EUROPE_BBOX` is defined in `ehd/config.py` but used nowhere.** In practice
"Europe" has meant "what NCEI filed under `measurements/europe/`" — which
includes Turkey and Cyprus but excludes all of European Russia. That is a
curatorial boundary, not a geographic one, and it is the largest bias found so
far: Eastern Europe is under-represented by construction.

## 3. re3data registry (2026-10-24)

API keyword search (`/api/beta/repositories?query=`): "dendrochronology" →
TreeSource only (Natural Resources Canada: forestry research installations,
tree-level data, open licence — North American scope, not examined further);
"tree ring" / "tree-ring" → NCEI Paleoclimatology only; "dendro", "DCCD",
"Digital Collaboratory" → nothing. **Not a usable denominator**: it does not
list DCCD at all, and general repositories that do hold tree-ring data
(PANGAEA, Zenodo) are not tagged for it. The registry's horizon is what
repositories chose to describe, so its silence says little. Source 4 has to be
searched directly.

## 4a. PANGAEA (2026-10-24)

The 2026-08-17 probe ("nothing relevant") was wrong: it searched for
Hohenheim by name. `parameter:"Tree ring width"` matches **53,084 datasets**,
almost all one timber each, from German dendrochronology laboratories:

| depositor (PANGAEA author) | datasets | what |
|---|---:|---|
| Hofmann, J (Jutta Hofmann) | ~19,600 | historical objects, SW Germany (sample: 51 of 150) |
| Bleyer, H-J | ~9,500 | historical objects (49 of 150) |
| Friedrich, M (Hohenheim, sample codes `HOH…`) | ~6,500 | mostly historical objects and some living trees; plus the **collection of 257 subfossil Late Glacial / Holocene *Pinus sylvestris*** (Friedrich, Kromer, Kaiser et al. 2001, `doi:10.1594/PANGAEA.787724`) |
| Preßler, E | ~4,800 | historical objects, Netherlands and northern Germany |

Counts are author-query totals (they overlap a little with co-authored sets)
plus a 150-dataset random sample by offset.

**Access: every one sampled (120 of 120) is restricted** — HTTP 401, "you need
to be authorized … contact the principal investigator". The Friedrich 2001
*collection* record is open (CC-BY 3.0); its member series are not.

**But the public metadata carries the dated span.** Each dataset's JSON-LD
`description` gives species, ring count and first/last year ("Species PISY;
No of rings 57; Begin 1717; End 1773"; Preßler's wording is "first year … end
year" or "tree-death year"), and `spatialCoverage` gives coordinates. 150 of
150 sampled had a parseable span. A timeline bar needs only span, taxon and
place, so these timbers could be drawn without the restricted ring widths —
but whether that is acceptable use of a restricted deposit (and of the EU
database right in the metadata) is a question for the depositors or PANGAEA,
not something to assume.

The 257 subfossil pines (all 258 records' public metadata read 2026-10-24):
**floating** — "Data are shown on a relative timescale as the chronology is
still floating. A tentative match on the INTCAL04-timescale is given in Kromer,
Friedrich et al. Radiocarbon 46(3), 2004" (the paper already tied to swit240).
Relative years 1201–2407, ~1,200 years; sites in Lusatia (51.39°N 14.71°E)
and Westphalia; DEKLIM project PROSIMUL I. Late Glacial, so it sits *before*
the 11746–5408 BC gap, not in it, and needs a calendar anchor like the Swiss
files. The Holocene Hohenheim oak and Preboreal pine series were not found on
PANGAEA by any query tried.

**Harvested 2026-10-24** (`python -m ehd.pangaea`; raw ES pages under
`raw/pangaea/treering`, parsed to `interim/pangaea_treering.json`): **53,094
records, equal to the index's own total.** Findings:

- The restricted series belong to project **HISTRA, "Historical and Postglacial
  Tree Ring Archive of Hohenheim"** (Institute of Botany, University of
  Hohenheim): Hofmann 19,567, Bleyer 9,129, Friedrich 6,427, Preßler 4,843 —
  i.e. this *is* the Hohenheim archive, deposited 2004–2012. Login option 3
  (restricted): 39,965.
- **Schweingruber** (WSL) ~13,000 series, login option 1 — *open*. Living
  trees; probably overlaps his ITRDB network heavily. Duplicate check needed
  before use.
- Spans parsed from the public comment lines: **51,549**; 1,418 "Age not
  determined"; 127 with no span; 257 floating (the Late Glacial pines).
- **Preßler's span is one year longer than his "No of rings" in 3,409 of 3,422
  dated records**, bark or no bark — a convention, not noise; which end is off
  cannot be told without the ring widths. Keep his years as stated, flag ±1.
  16 Friedrich records disagree by other amounts. 3 records have last < first
  (e.g. "Begin 4637; End 1699"): data-entry errors, exclude and report.
- The per-record "XML-file of tree-ring width" link on `store.pangaea.de` also
  answers 401: the restriction is consistent.

Zenodo: 54 datasets for `"tree-ring width"`, 101 for `dendrochronology`, 176
for `"ring width" dendrochronology` — small enough to triage by hand or with a
local model. Not yet examined.

## Open decision: what "Europe" means, and whether to go beyond it

**Decision (Howard, 2026-10-24):** gather data files from *everywhere* for
study (`python -m ehd.fetch --all` mirrors every `measurements/` folder), but
the web build stays regional for now: **expanded Europe** — Europe to the
Urals, plus Turkey, Cyprus, Georgia and North Africa, with the Sahara as the
southern edge. To be implemented as a test on site coordinates, not as an
ITRDB folder.

Not yet settled (raised 2026-10-24): the Levant (Lebanon 12 sites, Syria 4,
Jordan 4, Palestine 2 — between Cyprus/Turkey and North Africa); Armenia and
Azerbaijan beside Georgia; Iran's Caspian (Hyrcanian) forests; Macaronesia
(Canaries, Madeira, Azores). The Western Palearctic is the established
biogeographic unit with exactly the Sahara as its southern edge, and includes
all of these except, in most definitions, Iran. `EUROPE_BBOX` cannot express
it: its 34°N floor drops Moroccan sites down to 32.3°N, and a box that
reaches them takes in the Levant and Iraq whether wanted or not.

Options considered:

- **A. Geographic Europe**, applied to site coordinates across *all* ITRDB
  folders: needs a stated boundary (Urals crest / Ural River / Caspian /
  Caucasus / Bosporus; and whether Turkey, Cyprus, Georgia and the Maghreb
  are in). Brings in European Russia.
- **B. NCEI's folder as-is.** Simple, but inherits the folder's boundary.
- **C. Global.** Every boundary question above disappears; costs as discussed
  2026-10-24 (payload, map, name).

## 5. Analysis of the gathered data (2026-10-24)

Script: scratchpad `global_logs.py` — every regional ITRDB folder through the
project's own `select_files` + `parse_rwl` + `read_template_header`.
Cross-checks: it chooses exactly the build's 2,068 European files and yields
its 76,950 European series. **Global: 285,774 series**, 7,561 files chosen
(USA 108,138; Europe 76,950; Canada 35,347; Asia 32,205; South America 10,473;
Australia 9,001; Mexico 7,993; Africa 5,388). One file has no series.

**Earliest calendar-dated material anywhere in ITRDB:** only two collections
start before 5000 BC — ca535 (bristlecone, 6001 BC) and swed334 (5408 BC).
**Calendar coverage is continuous worldwide from 6001 BC to 2025** (some log
alive every year; coverage, not verified overlap). Floating collections that
declare BP ages outside Europe: **newz116** (Towai kauri, 92 series, declares
13125–11675 *cal yr BP* = 11175–9725 BC, inside the European gap; placement
presumably by 14C, to be checked) and **wi013** (Two Creeks, 21 series,
declares 12000–11750 cal yr BP; Two Creeks is usually put near 13.8 ka cal BP,
so this may be 14C years mislabelled — plausible, unchecked).

**Expanded Europe from ITRDB's other folders** (rough Western Palearctic test,
for counting only): Africa folder ~4,630 series / 90 sites (Algeria, Tunisia,
Morocco); Asia folder ~4,980 / 126 inside the 45°E box (European Russia,
Turkey-adjacent, Lebanon, Syria, Georgia) + 1,389 / 44 Russia 45–60°E + 153 / 7
Levant + 23 / 1 Caucasus; Iran's Caspian forests 0. Total ~11,200 series,
~270 sites (+15%). No `europe/` file falls outside the region.

**PANGAEA:**
- HISTRA (Hohenheim archive; Hofmann, Bleyer, Friedrich, Preßler): ~38,300
  dated timbers, 892–2011 CE, median start ~1500–1600, southern and central
  Germany plus Preßler's Netherlands/N Germany; spruce, fir, oak, pine.
  Nothing before 1 CE. One placeholder ("Begin 0; End 0") to exclude.
  Adds ~half again the corpus, concentrated in one region and era — say so
  on the site.
- **Schweingruber's 13,003 open series duplicate his ITRDB network**: at two
  sites checked whole, the multisets of spans are identical (BIS 30 samples =
  swit131's 30 series; CAPRA 20 = roma004's 20); ITRDB uses numeric series ids
  and coordinates differing by ~0.05–0.3°. Overall 95% match on span + place
  within 0.5° (86% with species). Do not import; useful only as a coordinate
  cross-check.
