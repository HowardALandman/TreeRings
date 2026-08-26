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
uv venv --python 3.12 && uv pip install pytest brotli   # once
python -m ehd.fetch      # download corpus (~5,600 files) to the data root
python -m ehd.harvest    # study metadata + corpus reconciliation report
python -m ehd.emit       # build web/data payloads
python -m ehd.validate   # cross-check parser against dplR + invariants
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

- 5,623 `.rwl` files listed in ITRDB `measurements/europe/`
- → 2,061 files after dedup, → **76,745 logs**, 76,529 plotted
- 216 logs withheld as floating; 23 plotted over a wrong declared span
  (`disputed`, and going to zero on the next harvest — NCEI fixed both
  collections, see below); 3,464 dated but unverifiable against metadata
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
8. **A declared span that disagrees with the data is an archive defect, but
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

## Verification

- `pytest tests/` — 59 tests: parser fixtures are the files that broke earlier
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
description, `og:description` and `og:title` all say 76,529, and nothing checks
them against `emit`'s actual `n_logs`. Same drift as `og.jpg` below, and the
same fix if it ever matters: have `emit` write the head, or at minimum assert
the number still matches. `og:title` is deliberately *not* the same string as
`og:site_name`; Facebook stacks the two and repeating the name prints it twice.

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

- **Floating chronologies.** 216 logs across 7 collections are withheld because
  their year column is ring ordinals: Kaiser's Daettnau pines (swit195–198, 41
  logs), Schaub & Kaiser's Gaenziloo/Landikon (swit240, 95), and Bebchuk et
  al.'s Fenland yews (brit099/brit100, 80). Absolute offsets exist outside the
  files (swit195 declares `-12287`; Reinig et al. redated the Swiss Late Glacial
  pines for IntCal20), so wiring those in would push the timeline past 12,000
  BP. Contact: Frank Reinig (Mainz) / Ulf Büntgen (Cambridge).
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
- **Metadata gaps.** 3,464 logs lack a declared span to check dating against.
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

  One residual: `fran10.rwl` header line 2 still ends `1943   1988` while the
  record and template say 1747–1988. The start year was not propagated into
  the file.

  **He answered the definitional question, and the answer inverts trap #8:**
  "The time ranges for the ITRDB studies should match the range of dates in the
  rwl file." A declared span that disagrees with the data is a defect, not a
  site chronology. He then asked for more: "Please let us know if you find any
  other studies whose age ranges do not match the rwl file age ranges."

  **Consequence for the pipeline:** the `disputed` class empties on the next
  harvest. Its 23 logs are exactly neth005 (9) + brit (14), and both records
  are now correct, so re-harvesting drops that class to zero and
  `tests/test_dating.py`'s comments describing those records in the present
  tense become false. Fix the comments when that happens; the test inputs are
  still valid as historical cases.

- **The sweep Ed asked for — next session, needs a fresh harvest first.**
  Scoped but not built. Ed is actively editing records, so the 2026-08-17
  `study_metadata.json` snapshot is stale and would report already-fixed rows;
  re-run `python -m ehd.harvest` before generating anything to send.

  Magnitude, measured against the stale snapshot (so ±4 studies), comparing
  each deduplicated `.rwl`'s measured span against its study record:

  ```
  1871  exact match          <- 92.2%, which is why the rule is real
    70  declared narrower (inside data)
    59  declared wider (data inside)
    20  declared offset (partial overlap)
     9  disjoint
    32  no study-record span
  ```

  158 files → 144 distinct studies → **~135 reportable**, after removing the
  two already fixed and seven that must *not* be "fixed":

  - **The 7 disjoint ones are the floating collections** (swit195–198, swit240,
    brit099, brit100). Their year column is ring ordinals and the study record
    holds the *only* absolute anchor — swit195 declares −12287. Applying "make
    the record match the rwl" to these destroys the placement. Warn him
    explicitly; this is the most important thing in the report.
  - **40 studies are off by exactly one year, and 22 are the same error**:
    correct start, end one year too late. Another 8 are end one year early;
    30 of the 40 are end-only. That reads as a fencepost bug in whatever
    derived the ranges, and is worth reporting as one item rather than 40.
  - 24 studies are off by >100 years, 41 by 11–100.

  Group the report as *systematic off-by-one* / *large discrepancies* /
  *do-not-touch floating*. Ask Howard whether to send all ~135 or hold at the
  >10-year subset (~65) before drafting. Coverage caveat to state in the mail:
  this covers `measurements/europe/` only, 2,061 files after dedup of 5,623
  listed, of which 2,029 have a study-record span at all — the other seven
  ITRDB regions are unexamined and the ~7% defect rate probably generalises.

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
