# EHD — European tree-ring archive visualizer

Interactive view of individual subfossil and historical tree logs on a shared
time axis: one rectangle per log, greedily packed into rows, coloured by taxon,
with hover tooltips and click-through to each log's measured ring-width curve.

**Status: M1 complete.** Full pipeline runs end to end, 74,063 logs render in the
browser, parser cross-validates against dplR at 100%.

## The Hohenheim question

The project was conceived around the 12,460-year Hohenheim oak+pine chronology.
**Its per-log data has never been published.** Verified by direct probe, not
inference:

| Source | Result |
|---|---|
| ITRDB / NCEI | no Hohenheim study; only 14 measurement studies worldwide start before 3000 BC |
| Zenodo, PANGAEA | nothing relevant |
| DCCD | dead (DNS failure) |
| Billamboz German Neolithic oak (GERM021–031) | averaged `.crn` chronologies only, no per-log data |
| Belfast Irish oak | in ITRDB only from 1531 CE |

The public record therefore has a ~6,800-year hole from roughly 10,800 BC to
4,000 BC. Decision (Howard, 2026-08-17): build the prototype on public ITRDB
data and pursue Hohenheim separately. The pipeline is source-agnostic, so a new
per-log corpus drops in as another input.

## Running it

```bash
uv venv --python 3.12 && uv pip install pytest      # once
python -m ehd.fetch      # download corpus (~5,600 files) to the data root
python -m ehd.harvest    # study metadata + corpus reconciliation report
python -m ehd.emit       # build web/data payloads
python -m ehd.validate   # cross-check parser against dplR + invariants
cd web && python -m http.server 8777                 # then open localhost:8777
```

Data root resolves to `$EHD_DATA`, else `/Volumes/Expansion/EHD`, else `./data`.
Note the external drive's *root* is `root:wheel` and not writable by `howard`;
`/Volumes/Expansion/EHD` had to be created once with sudo.

`python -m ehd.validate` needs R with dplR (`install.packages("dplR")`).

## What the numbers are

- 5,623 `.rwl` files listed in ITRDB `measurements/europe/`
- → 2,061 files after dedup, → **76,745 logs**, 74,063 plotted
- 2,682 logs withheld as floating; 3,464 dated but unverifiable against metadata
- Span 5407 BC – 2023 CE; 2,030 sites

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
7. **NCEI's `Continent>Europe` filter is unusable.** Of 6,000 studies it returns,
   only 1,541 have European coordinates; it also omits genuine European studies.
   The `measurements/europe/` directory listing defines the corpus instead.

## Verification

- `pytest tests/` — 20 tests, fixtures are the files that broke earlier parsers.
- `python -m ehd.validate` — **100.0000% span agreement with dplR on 65,154
  series**, 0 disagreements, 0 invariant failures, 0 series found by dplR that
  we miss (we additionally read 11,591 series dplR cannot).
- `ehd.emit` asserts the packing is overlap-free before writing.
- Palette validated with the dataviz skill's checker in both light and dark.

## Shape of the data (drives the UI)

The archive is overwhelmingly modern: 7 logs alive in 5000 BC, 80 at 1 CE,
**60,313 in 1971**. Packed, that is a ~60,000-row wedge, so the viewer zooms on
both axes and offers era filters. The "Before 1 CE" + "Packed together" view is
the classic overlapping-chronology ladder and the most legible entry point.

## Next

- **Floating chronologies.** 2,682 logs (incl. the Swiss Late Glacial pines,
  the oldest material available) are withheld because their rings number from 1.
  Absolute offsets exist in prose/headers (swit195 carries `-12287`); wiring
  those in would push the timeline back past 12,000 BP.
- **Taxon colour beyond 6 groups.** Only 3 hues can be distinguished at
  arbitrary adjacency; the by-taxon band layout is what makes 6 legal. Do not
  add hues without re-running the validator.
- **Hosting.** Payload is 3.35 MB core plus lazy shards — static hosting
  (GitHub Pages / Cloudflare Pages) is sufficient. Not yet set up.
- **Metadata gaps.** 3,464 logs lack a declared span to check dating against.
- Local LLMs are unused so far; the natural fit is tidying multi-language site
  and investigator strings for display.
