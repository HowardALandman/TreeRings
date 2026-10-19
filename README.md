# TreeRings

**[treerings.howardalandman.org](https://treerings.howardalandman.org)**

An interactive view of individual subfossil and historical tree logs on a shared
time axis. One rectangle per log, greedily packed into rows, coloured by taxon,
with hover tooltips and click-through to each log's measured ring-width curve.
A map view shows where the collections were taken, one pie per published
coordinate, linked to the timeline.

The corpus currently loaded is the ITRDB European measurement set —
**73,390 logs · 2,038 sites · 12429 BC – 2025 CE**. Europe is where this
started, not the limit of what it handles; see [Scope](#scope).

Most tree-ring resources publish *site chronologies* — averaged curves. This
shows the underlying measured series individually, which is what makes the
overlapping ladder of chronologies visible: you can see how the record is
assembled from them.

**What a "log" is.** One bar is one measured ring-width series — a core or a
radius — not necessarily one tree. A tree sampled with two cores is two bars,
because the archive has no field recording which series belong to the same
tree. The count also includes redundant copies: an audit of an earlier build
found about 2,000 series deposited byte-identically in more than one
collection, and about 600 in blue-intensity files that remeasure trees already
present. Merging both is planned but not done.

## Why the archive looks the way it does

The corpus is overwhelmingly modern: 7 logs alive in 5000 BC, 81 at 1 CE, and
58,976 in 1971. Packed together that is a ~59,000-row wedge, so the viewer zooms
on both axes and offers era filters. The **"Before 1 CE" + "Packed together"**
view is the classic overlapping-chronology ladder, and the most legible entry
point.

It also has a hole. No log is alive between 11746 BC and 5408 BC: before it
there are only the anchored French Late Glacial pines, after it continuous
coverage. The long Central European oak and pine chronology (Hohenheim) covers
most of that interval, but its per-log measurements have not been published.

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
uv venv --python 3.12 && uv pip install pytest brotli   # once
python -m ehd.fetch      # download corpus (~5,600 files) to the data root
python -m ehd.harvest    # study metadata + corpus reconciliation report
python -m ehd.emit       # build web/data payloads
python -m ehd.basemap    # map outlines from Natural Earth (pinned, checksummed)
python -m ehd.validate   # cross-check parser against dplR + invariants
python scripts/serve.py  # view at localhost:8777
```

`scripts/serve.py` rather than `python -m http.server`, because `ehd.emit`
writes the two first-paint payloads brotli-compressed under their plain names
and `web/_headers` is what declares that to the browser; the dev server reads
the same file, so local and deployed behaviour match. A plain static server
hands the viewer compressed bytes and it draws nothing.

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
- **A declared span that disagrees with the data is a metadata defect**, not a
  site chronology narrower than its longest log — NCEI confirmed the study's
  age range should match the `.rwl` file. Disagreements are common, though (the
  first sweep found 152 files), so dating classification tests overlap rather
  than endpoint agreement, and `ehd.sweep` reports the mismatches upstream.

Verification:

- `pytest tests/` — 152 tests; the parser fixtures are the files that broke
  earlier parsers.
- `python -m ehd.validate` — **100.0000% span agreement with dplR across 65,438
  series**, 0 disagreements, 0 invariant failures, and 0 series found by dplR
  that this parser misses. It additionally reads 11,512 series dplR cannot
  (run 2026-10-19, dplR 1.7.9).
- `ehd.emit` asserts the packing is overlap-free before writing.

## Payload size

The two files first paint waits on are written brotli-compressed at quality 11
and served with `Content-Encoding: br`. `logs.bin` is `application/octet-stream`,
which Cloudflare's auto-compression allowlist excludes, so it shipped raw at 84%
of first load; `index.json` was compressed, but by an edge encoder tuned for
speed rather than ratio. Pre-compressing both takes first load from 2,192,561 to
678,710 bytes — 2.09 MiB to 0.64 MiB, 69% smaller — measured live rather than
locally, since the ratio a CDN serves is not the ratio a build produces
(2026-08-20, on that day's build). The map's coastline file (~440 KB) is not
part of first load; it is fetched the first time the map is opened.

Clients that do not accept brotli are not stranded: Cloudflare decodes and
re-encodes at the edge, so an `Accept-Encoding: gzip` request still gets gzip and
one with no `Accept-Encoding` gets the raw bytes.

The compression and the `_headers` rule break the site if separated, so
`tests/test_headers.py` pins them together and `app.js` checks `logs.bin`'s
length against `n_logs` and names the likely cause if it ever mismatches.

## Dating status

Logs are labelled rather than silently mixed:

- **absolutely dated** — calendar-dated and consistent with archive metadata
  (73,036)
- **anchored** — a floating collection placed on the calendar by a reviewed
  anchor taken from its depositors' own dating statement, carried with its
  uncertainty (191, across 5 collections: the French Late Glacial pines
  fra053–055 and the Fenland yews brit099–100). The build fails if a file
  stops reproducing its declared span, so an anchor cannot silently go stale.
- **unverified** — dated, but no declared span exists to check against (86,
  across 3 collections)
- **disputed** — plotted over a declared span the data contradicts (77, across
  2 collections whose records end in 1928 while their data runs to 2025; each
  case is reviewed by hand)
- **floating** — withheld from the timeline entirely; the year column holds ring
  ordinals, not calendar years (136, across 5 Swiss Late Glacial collections)

Logs from studies NCEI has withdrawn are parsed and validated but never drawn
(3,424 logs, 25 studies).

The Swiss Late Glacial pines have been placed on the calendar in the literature
by radiocarbon wiggle-matching, but no per-file anchor appears anywhere in the
archive, so they stay floating until a placement can be tied to each file.

## Data source and credit

All measurements come from the [NOAA/NCEI International Tree-Ring Data
Bank](https://www.ncei.noaa.gov/products/paleoclimatology/tree-ring), contributed
by the many investigators credited in each site record and reachable through the
study links in the viewer. This project neither collected nor re-measured any
rings; it parses, reconciles, and displays their published data.

Metadata defects found during reconciliation have been reported to NCEI, which
has been correcting them — see `docs/ncei-metadata-report.md` and the
study-by-study sweep in `docs/ncei-sweep-2026-08.txt` (`python -m ehd.sweep`
reruns it).

## License

Code: [MIT](LICENSE). The underlying ITRDB measurements are NOAA public-domain
data and are not redistributed by this repository — `ehd.fetch` downloads them.
