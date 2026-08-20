# TreeRings

**[treerings.howardalandman.org](https://treerings.howardalandman.org)**

An interactive view of individual subfossil and historical tree logs on a shared
time axis. One rectangle per log, greedily packed into rows, coloured by taxon,
with hover tooltips and click-through to each log's measured ring-width curve.

The corpus currently loaded is the ITRDB European measurement set —
**76,529 logs · 2,054 sites · 5407 BC – 2023 CE**. Europe is where this started,
not the limit of what it handles; see [Scope](#scope).

Most tree-ring resources publish *site chronologies* — averaged curves. This
shows the underlying logs individually, which is what makes the overlapping
ladder of chronologies visible: each bar is one tree, and you can see how the
record is assembled from them.

## Why the archive looks the way it does

The corpus is overwhelmingly modern: 7 logs alive in 5000 BC, 84 at 1 CE, and
62,199 in 1971. Packed together that is a ~62,000-row wedge, so the viewer zooms
on both axes and offers era filters. The **"Before 1 CE" + "Packed together"**
view is the classic overlapping-chronology ladder, and the most legible entry
point.

## Scope

ITRDB publishes measurements under regional directories: `africa`, `asia`,
`atlantic`, `australia`, `centralamerica`, `europe`, `northamerica`, and
`southamerica`. This project reads `europe` today.

Nothing downstream of the fetch is Europe-specific. The `.rwl` parser, the
duplicate reconciliation, the dating classifier, the packing, and the viewer all
operate on logs without reference to region. Adding another regional corpus is a
matter of parameterising the region — it is currently hardcoded in
`ehd/config.py` (`ITRDB_EUROPE`) and `ehd/fetch.py` (`list_europe_files`,
and the `raw/itrdb/europe` destination) — plus deciding how the viewer should
present a corpus large enough that a single packed timeline stops being legible.

The pipeline is also source-agnostic beyond ITRDB: any per-log corpus that can be
expressed as series with ring widths and a dating status drops in as another
input.

## Running the pipeline

```bash
uv venv --python 3.12 && uv pip install pytest   # once
python -m ehd.fetch      # download corpus (~5,600 files) to the data root
python -m ehd.harvest    # study metadata + corpus reconciliation report
python -m ehd.emit       # build web/data payloads
python -m ehd.validate   # cross-check parser against dplR + invariants
cd web && python -m http.server 8777
```

Data root resolves to `$EHD_DATA`, else `/Volumes/Expansion/EHD`, else `./data`.
`ehd.validate` additionally needs R with [dplR](https://github.com/AndyBunn/dplR).

The pipeline is source-agnostic: a new per-log corpus drops in as another input.

## Correctness

The `.rwl` format has traps that silently corrupt results rather than failing
loudly. Each of the following was found in real corpus files, and each has a
regression test in `tests/`:

- **RWL is fixed-width.** IDs run straight into the year (`0003401Q1890`); a
  whitespace parser fails on ~32% of the corpus.
- **BC years borrow column 8** for the minus sign (`C002   -2894`).
- **`-999` is a missing ring, not a terminator.** It appears mid-series in long
  runs; treating it as terminal truncated one 1854–2010 log to 1854–1864.
- **The terminator is per-file.** In a 0.001 mm file, `999` is a real 0.999 mm
  ring, so terminators are trimmed from series *ends* rather than acted on inline.
- **Trailing locally-absent rings** (negative flags such as `-8`) must not extend
  a span; interior ones are real zero-width rings.
- **Three kinds of duplicate** — `-noaa.rwl` re-encodings, per-variable suffixes
  measured on the same trees, and series IDs repeated across sites. Left alone
  these inflate the log count by ~36%.
- **A declared span narrower than the data is normal.** The declared span
  describes the site chronology, not the longest log, so dating classification
  tests overlap rather than endpoint agreement.

Verification:

- `pytest tests/` — 40 tests; the parser fixtures are the files that broke
  earlier parsers.
- `python -m ehd.validate` — **100.0000% span agreement with dplR across 65,154
  series**, 0 disagreements, 0 invariant failures, and 0 series found by dplR
  that this parser misses. It additionally reads 11,591 series dplR cannot.
- `ehd.emit` asserts the packing is overlap-free before writing.

## Dating status

Logs are labelled rather than silently mixed:

- **absolutely dated** — calendar-dated and consistent with archive metadata
- **unverified** — dated, but no declared span exists to check against (3,464)
- **disputed** — plotted over a declared span the data contradicts (23)
- **floating** — withheld from the timeline entirely; the year column holds ring
  ordinals, not calendar years (216, across 7 collections)

Absolute offsets for several floating collections exist outside the files, so
wiring them in would extend the timeline well past 12,000 BP. Not yet done.

## Data source and credit

All measurements come from the [NOAA/NCEI International Tree-Ring Data
Bank](https://www.ncei.noaa.gov/products/paleoclimatology/tree-ring), contributed
by the many investigators credited in each site record and reachable through the
study links in the viewer. This project neither collected nor re-measured any
rings; it parses, reconciles, and displays their published data.

Known metadata defects found during reconciliation have been reported to NCEI —
see `docs/ncei-metadata-report.md`.

## License

Code: [MIT](LICENSE). The underlying ITRDB measurements are NOAA public-domain
data and are not redistributed by this repository — `ehd.fetch` downloads them.
