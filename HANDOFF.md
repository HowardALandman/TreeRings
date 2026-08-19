# EHD — European tree-ring archive visualizer

Interactive view of individual subfossil and historical tree logs on a shared
time axis: one rectangle per log, greedily packed into rows, coloured by taxon,
with hover tooltips and click-through to each log's measured ring-width curve.

**Status: M1 complete.** Full pipeline runs end to end, 76,529 logs render in the
browser, parser cross-validates against dplR at 100%.

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

- 5,623 `.rwl` files listed in ITRDB `measurements/europe/`
- → 2,061 files after dedup, → **76,745 logs**, 76,529 plotted
- 216 logs withheld as floating; 23 plotted over a wrong declared span
  (`disputed`); 3,464 dated but unverifiable against metadata
- Span 5407 BC – 2023 CE; 2,054 sites

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
8. **A declared span narrower than the data is normal, not a sign of relative
   dating.** The declared span describes the site chronology, not the longest
   log: fran10 declares 1943–1975 and measures 1747–1988. The first classifier
   demanded endpoint agreement and so called 2,682 logs floating when only 216
   are; overlap is the right test. See `tests/test_dating.py`.

## Verification

- `pytest tests/` — 40 tests: parser fixtures are the files that broke earlier
  parsers; `test_dating.py` pins every real collection the classifier must
  separate into absolute / floating / disputed.
- `python -m ehd.validate` — **100.0000% span agreement with dplR on 65,154
  series**, 0 disagreements, 0 invariant failures, 0 series found by dplR that
  we miss (we additionally read 11,591 series dplR cannot).
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

Verified post-deploy: all 7 fetch paths 200, http→https 301, `_headers` applied
(`no-cache` + nosniff/Referrer-Policy/X-Frame-Options), gzip on everything except
`logs.bin` (see Next), 76,529 logs render, lazy shard fetch draws the sparkline,
browser console clean.

## Shape of the data (drives the UI)

The archive is overwhelmingly modern: 7 logs alive in 5000 BC, 84 at 1 CE,
**62,199 in 1971**. Packed, that is a ~62,000-row wedge, so the viewer zooms on
both axes and offers era filters. The "Before 1 CE" + "Packed together" view is
the classic overlapping-chronology ladder and the most legible entry point.

## Next

- **Floating chronologies.** 216 logs across 7 collections are withheld because
  their year column is ring ordinals: Kaiser's Daettnau pines (swit195–198, 41
  logs), Schaub & Kaiser's Gaenziloo/Landikon (swit240, 95), and Bebchuk et
  al.'s Fenland yews (brit099/brit100, 80). Absolute offsets exist outside the
  files (swit195 declares `-12287`; Reinig et al. redated the Swiss Late Glacial
  pines for IntCal20), so wiring those in would push the timeline past 12,000
  BP. Contact: Frank Reinig (Mainz) / Ulf Büntgen (Cambridge).
- **Taxon colour beyond 6 groups.** Only 3 hues can be distinguished at
  arbitrary adjacency; the by-taxon band layout is what makes 6 legal. Do not
  add hues without re-running the validator.
- **`logs.bin` ships uncompressed.** Cloudflare's auto-compression works from a
  content-type allowlist that excludes `application/octet-stream`, so the 1.84 MB
  binary is served raw where it would gzip to ~607 KB — every first visit pays
  ~1.2 MB extra. Neither fix is free: overriding the declared content-type to
  something on the allowlist works but is semantically false, and pre-compressing
  needs a `DecompressionStream` in `app.js`. Unresolved.
- **Metadata gaps.** 3,464 logs lack a declared span to check dating against.
- **Metadata defects reported to `paleo@noaa.gov`** — sent 2026-08-19 (Howard
  edited and added to the draft before sending); awaiting reply. See
  `docs/ncei-metadata-report.md`. Re-checked live against the study
  API on 2026-08-18:
  - **BRIT101** (study 44081): the search record says `271 276`; the file's own
    header says `271 726` and the data ends at 726. The file is right, and the
    NOAA template sibling carries no year fields — the defect is in the search
    database alone.
  - **NETH005** (study 3626): declares −66…106, data measures 1834–2006 — off
    by exactly 1900. Wrong in both the study record and `neth005-rwl-noaa.txt`
    (which states `Time_Unit: AD`).
  - **BRIT** (study 4225): declares 1750–1975, data measures 812–1458; wrong in
    the record, the template, and the `.rwl` header. The file also mixes three
    site codes (346 at 902–1203, 347 at 1131–1458, 348 at 812–1080) where the
    header describes 346 only.
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
