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
| 4 | General data repositories: Zenodo, PANGAEA, Dryad, Figshare, DANS Data Stations | search by keyword | PANGAEA sized 2026-10-24 (below); Zenodo searched by keyword 2026-11-01 (4d); DANS and DataverseNL harvested 2026-11-01 (4c); Dryad: only Zhao et al. checked, 2026-10-31 (below); Figshare: one title search, 18 hits, not enumerated |
| 5 | Literature inventories: Reinig et al. 2018 Late Glacial inventory, IntCal20 tree-ring data list, regional long-chronology reviews | published lists of chronologies, which name their data holders | IntCal20 archive (IntChron) inventoried 2026-10-31 (below); others not started |
| 6 | Named labs and national databases (DCCD, WSL, CEZA, Belfast, Innsbruck, Göttingen, Helsinki, …) | from 3 and 5, not from memory | DCCD found 2026-11-01 (4c); others not started |

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

## 4b. Zhao et al. 2019 on Dryad (2026-10-31)

`doi:10.5061/dryad.kh0qh06`, ITRDB v7.13, files dated January 2018. Its `Appendix
S1.zip` **is** our `raw/itrdb/zhao2018/AppendixS1.zip`: same size, same MD5 as
Dryad's digest (`ce579daf…`). **No new data for us.** Compared with today's
mirror (19,091 `.rwl`, 383,447 series, through `ehd.rwl`):

- Cleaned: 258,336 series, 253,201 value-identical. Across all three partitions,
  no site is absent today. Of the 5,900 not identical, 263 are renumbered copies,
  4,963 correlate at r >= 0.98 with a same-site series on the same years; 674
  remain, 544 of them in the removed "duplicated" set.
- Cleaned series with no match: 101, earliest 696 CE. Cleaned + conflictive in
  Europe/Africa: 7 (aust003, neth005, germ4, ital017, fran009). Not chased.
- Two apparent old-data hits are artefacts: its conflictive `ca535` has the BC
  year one column right (same 21,594 lines as today's file), and `swit177*` in
  "duplicated" is zero-padded from year 0 (real span 982-1976).
- It predates fra053-055, swed334 and brit099, and **holds 3,206 series from 21
  sites since withdrawn** (`KNOWN_WITHDRAWN`). Do not ingest it. It is useful
  only as a 2018 snapshot for seeing what NCEI changed later.

## 4c. DCCD on DataverseNL and DANS (2026-11-01)

The DCCD did not vanish: its contents moved. `dendro.dans.knaw.nl` is dead, but
**DataverseNL** holds the collections. Harvested through the Dataverse search and
native APIs (10 queries, union 4,282 datasets, no errors): **4,260 carry the `dccd`
metadata block, with 30,135 measurement files (28,620 `.fh`, 1,360 `.d`, 155 `.rwl`)
listed; 4,049 of them restricted.**

**Denominator:** the 18 parent collections found by two of the queries hold 4,264
datasets by subtree count, against 4,260; the 4 are not reconciled. Files are not
series: `.fh` files can hold several (1, 24, 38 in the three opened), so **the
series count is unknown**.

**Access, open measurement files:**

| guestbook | CC BY-NC-ND 4.0 | CC0 |
|---|---:|---:|
| required | 21,313 | 246 |
| none | 4,506 | 21 |

The guestbook (ids 24, 25, 26; id 24 read from the API) requires name, email and
institution, plus the query date and why you are interested, and asks that follow-up
results be shared in DataverseNL/DCCD. Without a response the API refuses the file.
**No response has been filed**: it is a personal statement, Howard's to make. Whether
drawing derived bars and curves fits NoDerivatives is also his call or the
depositors'. Only guestbook 24's fields were read, and the refusal was seen on it alone.

**Period (`dccd-period`, 2,833 of 4,260; the other 1,427 have none):**

| period starts at or before | datasets | open files | of which no guestbook |
|---|---:|---:|---:|
| 1 CE (year 0) | 484 | 6,919 | 3,270 |
| -1000 | 118 | 1,348 | 110 |
| -3000 | 47 | 700 | 5 |
| -5000 | 13 | 376 | 1 |
| -5408 | 9 | 287 | 0 |
| -6000 | 1 | 117 | 0 |

Oldest: `10.34894/RF5NZF` Roderwolde Stobbenven, -6401..-6059 (117 files), then De
Deelen (Friesland), Wildervank and Hardinxveld bog oaks. Nothing starts before -7000.
These periods are depositor metadata; the oldest nine have not been opened.

**Checked on the data (3 no-guestbook datasets):** `.fh` `DateEnd` and `Length` match
the metadata at the ends compared: Z50SPH -5278..-5073 exactly, SUDGGD's -4459 start,
WDKEUR's -894..-662.

**First gated file read: `tridas.xml` of RF5NZF (Roderwolde), downloaded by Howard
2026-11-01, stored under `raw/dccd/RF5NZF/`, not ingested.** His browser showed an
Anubis bot check, then a "Dataset Terms" popup with the CC BY-NC-ND 4.0 notice,
citation instructions and an Accept button, and no input fields as far as he could see.
The API refuses this dataset's files without a guestbook response and the guestbook
marks name, email and institution required, so the browser route does not collect what
the guestbook defines; why is unknown, and network traffic was not inspected. Tell the
depositors; do not use this route for bulk download.

`originalvalues/2013052 Roderwolde Stobbenven.xml` (also stored) is an **older version
with no widths**: same 117 series, project last modified 2014-06-03 against 2016-12-13
in `tridas.xml`. Of 37 series dated in `tridas.xml`, 19 have the same dates, 17 pines
move one year later in the newer file (e.g. RWD00240 BC 6337 to 6336, as the erratum
says), and RWD00330 is dated only in the newer. **So a dataset's dates can differ by
file: use `tridas.xml`, and expect revisions.**

`.fh` against `tridas.xml` for RWD00240, 00330, 00440 (the first a control):
- Widths identical over `Length` in all three. The `.fh` data then pads with zeros to a
  full line, so those zeros are padding here and `Length` must be used, not the count.
- The `.fh` dates are the **older** ones: 00240 `DateEnd=-6215` (2014 BC 6215, 2016 BC
  6214); 00330 `DateEnd=108`, undated. So `.fh` here was not updated in 2016.
- **`-N` in `.fh` means N BC, not astronomical** (2 of 2: 00240, 00440). Astronomical is
  `1 - N`. A build reading `DateEnd` as astronomical is one year off. 3 files, 1 dataset.
- **The 2016 ring corrections are not in the deposited widths** (crossdating test on
  `tridas.xml`; first differences of log width against the mean of the other 32 dated
  pines, lags -3..+3). `2013052 addendum EJ.docx` only repeats the comment.

  | segment | r at current date | best lag, r |
  |---|---:|---|
  | 00330 rings 1-71 | 0.40 | -1, 0.69 |
  | 00330 rings 72-end | 0.54 | 0 |
  | 00440 rings 1-110 | 0.08 | +1, 0.63 |
  | 00440 rings 112-end | 0.63 | 0 |

  Exactly what the comment predicts: adding a ring after 71 moves the early part back a
  year (start BC 6167), and removing ring 111 moves it forward (start BC 6263). Not
  tested: the ring position itself; only one split per series. Controls, 6 other long
  pines split the same way: 10 of 12 segments best at 0, but **RWD00830 rings 72-end
  prefer -1 (0.60 against 0.41)** and RWD00290 rings 72-end weakly (0.33 against 0.23),
  so there may be other one-year slips. The master contains the series above, not
  corrected. Do not silently fix any of these; show the deposited values and flag them.
- `.fh` carries things TRiDaS may not: 00330 ring 33 `;;wound`; 00240 `FirstValidRing=33`,
  `LastValidRing=87` of 123. Meaning, and whether TRiDaS keeps them, not checked. One file holds all 117
series with widths, equal to the dataset's 117 `.fh` by count (contents not compared);
so `tridas.xml` may be the only file needed per dataset. 37 series dated (36 at BC
6402-6058, one BC 3052-2901), 80 with no date. 101 *Pinus sylvestris*, 16 *Quercus*.
No series shares a 20-ring window with mirror series starting before 1000 CE.
- TRiDaS years are true BC: the depositor's erratum gives the pine calendar as 6336
  to 6058 BC, and the file's pines run exactly that. Astronomical = 1 - BC.
- Errors to handle: `RWD00330` ends "AD 6059", evidently BC (108 rings fit BC 6166 to
  6059). The project comment says `RDW00330` needs a ring added and `RDW00440` one
  removed; whether that was done is unknown. IDs mix `RDW` and `RWD`.

**Unresolved:**
- Year convention of the other fields. `dccd-period` here is -6401..-6059: the start
  fits astronomical (BC 6402), the end fits neither (the file reaches BC 6058 = -6057).
  In DLU1BF a series with identical values is `DateEnd=-2` in `.fh` and BC 48 to
  "AD 0" in `tridas.xml`. Read dates from TRiDaS only after checking them per dataset.
- Zeros occur in the widths (0-8 per series in those samples); meaning not checked.
- Overlap with the mirror and with PANGAEA HISTRA **not tested**. Preßler, for one,
  deposited in both DCCD and PANGAEA.

**DANS Data Stations** (`archaeology.datastations.nl`): 2008 "DCCD - contribution ..."
datasets (Stichting Ring 3,670 `.dat`; Haneca, Pressler, WUR and others in `.fh`),
DANS Licence, nearly every data file restricted. Possibly older copies of the above;
not compared. Searches on two other stations found only 2 modern-climate datasets.

## 4d. Zenodo (2026-11-01)

Six keyword queries, `type=dataset`. Five enumerated to the end; **`"tree-ring"
measurements raw` matched 75,628 of mostly noise and stopped at Zenodo's page limit**,
so that one is truncated. 41 records have `.rwl/.fh/.tuc` by file name. Contents of
`.zip` and `.rar` files not inspected, and `.xlsx`/`.d` holders found only by title.

**`10.5281/zenodo.1326474` (Land, Remmele et al. 2018), CC BY 4.0, open:** 540
subfossil oaks, Main region, Germany. **-6227..-4056** (matches the stated 6228-4057
BCE), 2,172 years with no holes, 0.01 mm. 157 start at or before -5408; 111 end before
it. **No overlap**: 0 exact, 0 sharing a 20-ring window with any of 382,245 mirror
series that start before 1000 CE. Site code `EBEN` resembles IntCal's Ebensfeld timbers, so
this may be Hohenheim material (a guess, unchecked).

**Ingested 2026-11-01, deployed 2026-11-02** (`ehd/zenodo.py`). Against the
previous payload: 0 logs lost, 540 added, no existing site record changed. Shards
equal an independent scanner's reading on all 540. Plotted logs now leave
-11744..-6228 uncovered. dplR not run on this file. 472 logs have numbered display
IDs (`ALTE (2)`), since the file's IDs do not name trees. In BC lines the sign takes
column 8, so 3-digit tree numbers may have lost a digit (`STEI 13` x 9; plausible,
unchecked). Position is the middle of the stated region, not a site.

**`10.5281/zenodo.1453330` (Land et al. 2019), CC BY 4.0, open:** not ingested; 1,405 oaks, -320..2016,
same format. 0 exact matches in the mirror; the window test covered only mirror series
before 1000 CE, so partial overlap with later ones is untested. HISTRA overlap untested.

**`ehd.rwl.parse_rwl` undercounts both**: 196 of 540 and 1,384 of 1,405, because it
merges repeated IDs (it warns). IDs here are not unique within a file. Split on the
`999` stop markers instead; counts above come from that.

Others:
- `13736704` Edvardsson et al., southern Scandinavian oak, CC BY 4.0: seven `Raw_TRW`
  sheets of one column each, reaching -6028; these look like means, not logs (plausible,
  unchecked). Appendix A names 378 sites and 1,249 samples.
- `12698547` peatland subfossil, southern Sweden (404 samples, to 4931 BCE): restricted.
- `7419759` Seda River, Latvia: means only, out of scope.
- `10981405` Dispilio: description promises `.fh`; not in the `.rar`, PDF not opened.
- `18828071` Agios Vasileios and the listed `.fh`/`.rwl` holders: not opened.

## 4e. Other claims checked (2026-11-01)

**Formats.** "DCCEE" has no hits (one search; probably garbled DCCD, a guess). `.heg`
and "Hohenheim format": no hits; the Heidelberg format is `.fh`, from TSAP. Heidelberg
is not Hohenheim. `.dxf`: nothing found. `tridas.org` now serves a gambling site: do
not use. TRiDaS itself is alive inside DCCD datasets (`tridas.xml`).

**Neotoma: no dendrochronology constituent database.** API, `dbtables`: 44 constituent
databases and 46 dataset types, none for tree rings; taxon and site name searches
empty. "Dendrochronologic" exists only as a chronology-control type. Individual
sites using it were not examined, but no dataset type could hold ring widths.

**GitHub.** Unauthenticated, so repository search only, no code search. Six repos
listed: `RonaldVisser/ProvenanceNetworks` has 3 `.fh` and site-chronology tables,
`ropensci/fellingdater` 1 example `.fh`, the others none. 852 `rwl` hits unexamined.

**Journal supplements.** Of 127 DOIs cited by IntChron records, DataCite links 82
records, mostly false-positive marine sets; first 60 read. Tree-relevant ones look
like 14C, not widths (plausible, unchecked). **Cambridge's own supplement files were
not enumerated** (publisher blocks curl).

## 5a. IntCal20 archive on IntChron (2026-10-31)

`https://intchron.org/archive/IntCal/IntCal20/index.json`, 136 records, read
whole. Mostly 14C measurements, but it also holds what ITRDB and PANGAEA do not.
Horizon: IntCal20 only. Not looked at: other IntChron hosts, IntCal13 and earlier,
journal supplements. **Unresolved:** 13,054 dendro `IntCal_Data` points here
against 10,709 (9,211 + 1,498) in the IntCal20 tree-ring paper.

**Axis, verified:** `t + calage = 1950.5` (11,768 of 15,072 points; the rest not
examined), and `floor(t)` is the astronomical year: exact copies of ITRDB series
agree (ALTB05A t 1225.5 = 1225; CMC03L t -1236.5 = -1237; ST846A -2648.5 = -2649).

**Per-tree ring widths:** 109 `Dendro_Sample` series, 64 European, of which 25 are
exact copies of a series in the mirror, so 39 are new. 15 European logs fall in
the 11746-5408 BC gap (GAEN 6, KHWI 3, BINZ 2, LAND 2, COTT, BREI); 14 are new.
Together they reach only -11254..-9913, 1,341 of the gap's 6,337 years.

**SWIT240 anchor candidate:** `GAEN0071` = `swit240` `GAE071N`: all 436 widths
equal (0.01 mm), ordinals 889-1324. That gives **year = ordinal - 12143**, so the
file (53-1434) sits at -12090..-10709 = 12091-10710 BC. Status: one tree, a
proposal, **not applied to `anchors.py`**.
- Second test: HD_DE_Late_Glacial labels `G<n>_r<a>-<b>`, *assuming* G<n> =
  GAE<n>: implied offsets -12150 (13), -12142 (15), -12132 (2), -12178 (1, G54).
  So 9 of 10 trees agree within about 10 years; G54 is the exception, unexplained.
  G71 is GAEN0071 itself; the 8 other trees all give -12150, 7 years from the
  anchor. Their `t` looks rounded to decades (plausible, unchecked), which might
  account for that split, but it is unexplained.
- Depositors call the position "approx. BP"; `t_sigma` is 4 on the GAEN record.
- It contradicts the template's declared 15000-14000 BP by about 960 years. That
  declaration is already refused as rounded, and needs a human answer.
- Daettnau (swit195-198, 41 logs) stays floating: the only two labels mapping to a
  series imply offsets 128 years apart (`K213` -12008, `D203` -11880), and that
  mapping is a guess. `Daet304`, `K261` have no series in the files.

**Named timbers, no widths:** 14C labels give 435 European names with ring ranges
(`Ebensfeld 53_r108-117`), 213 touching the gap, spanning 5,487 of its 6,337 years
(all European dendro samples at +/-5 yr: 6,055). These are sampled portions, not
log spans; some names may be one tree (`Pfuhl22`, `Pfuhl22alt`, `Pfuhl22neu`); QL
and UB labels number rings on a master chronology. Drawing them as logs would
misstate them. They do name the wood and who dated it.

**Terms:** no licence found on the IntChron and IntCal pages checked. The
metadata's statistics tables end in a `Public` column reading `No` (52 of 52 found,
on rows naming a reference chronology, so it may mean the reference, not the
series attached). Ask before redistributing. Per-record metadata (single tree?,
dating method, t-values, archive) is good and could be shown if allowed.

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
