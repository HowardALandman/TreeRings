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
| 2 | NCEI paleo study search API, tree-ring studies by location | NCEI metadata, independent of folder layout | not started |
| 3 | re3data.org registry: repositories tagged dendrochronology / tree rings | repository registry | not started |
| 4 | General data repositories: Zenodo, PANGAEA, Dryad, Figshare, DANS Data Stations | search by keyword | Zenodo and PANGAEA probed 2026-08-17 for Hohenheim only — redo for everything |
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

## Open decision: beyond Europe?

See the conversation of 2026-10-24; record Howard's decision here.
