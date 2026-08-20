"""Build the static payloads the web viewer loads.

Geometry goes into a flat Int32 buffer because 76k rectangles as JSON objects
would be tens of megabytes and slow to parse; metadata that the viewer only
needs on hover or click stays in JSON, and per-log ring widths are sharded by
site so a click fetches ~30 KB instead of ~60 MB.

The two files first paint waits on -- logs.bin and index.json -- are written
brotli-compressed under their plain names and served with `Content-Encoding:
br`; see ehd/compress.py for why, and web/_headers for the rule.  They are
therefore not readable with `cat`, and a plain static file server will not
serve them correctly -- use `python scripts/serve.py` for local viewing.  The
values/ shards are left uncompressed: Cloudflare compresses application/json on
the fly, and 2,056 files at quality 11 is not worth the build time.

Usage:
    python -m ehd.emit
"""

from __future__ import annotations

import array
import json
import os
import sys

from . import compress, config, corpus, pack

# Band order on screen.  This is also the categorical colour order, chosen so
# that the three warm hues are never adjacent - see the palette validation in
# web/app.js.
GROUP_ORDER = ["pine", "oak", "spruce", "larch", "fir", "beech", "other"]

# Fields per log in logs.bin, in order.
FIELDS = ["start", "end", "row_unified", "row_band", "group_idx", "site_idx"]


def group_of(log: corpus.Log) -> str:
    return log.group if log.group in GROUP_ORDER else "other"


def main(argv: list[str] | None = None) -> int:
    web_data = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "data"
    )
    os.makedirs(os.path.join(web_data, "values"), exist_ok=True)

    # Check this before the corpus build rather than after it: the build takes
    # minutes, and a missing compressor is a one-line fix.
    backend = compress.backend()
    if backend is None:
        print(
            "no brotli available: `uv pip install brotli`, or install the "
            "brotli command-line tool (`brew install brotli`)",
            file=sys.stderr,
        )
        return 1
    print(f"compressing payloads with {backend} -q{compress.QUALITY}")

    print("building corpus...")
    logs, stats = corpus.build_logs()
    print(f"  {len(logs)} logs from {stats.n_files_used} files")

    # Floating collections number their rings from 1, so they carry no calendar
    # position.  Drawing them on the time axis would put Late Glacial pines in
    # the Roman period, so they are held back and reported instead.
    plotted = [log for log in logs if log.dating != "floating"]
    floating = [log for log in logs if log.dating == "floating"]
    disputed = [log for log in logs if log.dating == "disputed"]
    print(f"  {len(plotted)} plotted, {len(floating)} withheld as floating")
    print(f"  {len(disputed)} plotted with a disputed declared span")
    for site in sorted({log.site for log in disputed}):
        print(f"    {site}")

    # Stable site index, so the buffer can refer to metadata by integer.
    sites = sorted({log.site for log in plotted})
    site_idx = {s: i for i, s in enumerate(sites)}

    print("packing...")
    unified = pack.pack([(log.key, log.first_year, log.last_year) for log in plotted])
    row_unified = {p.key: p.row for p in unified}

    grouped: dict[str, list[tuple[str, int, int]]] = {}
    for log in plotted:
        grouped.setdefault(group_of(log), []).append(
            (log.key, log.first_year, log.last_year)
        )
    banded, heights = pack.pack_grouped(grouped)
    row_band = {p.key: p.row for p in banded}

    overlaps = pack.find_overlaps(unified) + pack.find_overlaps(banded)
    print(f"  unified rows: {pack.row_count(unified)}")
    print(f"  band heights: {[(g, heights.get(g, 0)) for g in GROUP_ORDER]}")
    print(f"  overlap violations: {len(overlaps)}")
    if overlaps:
        print("  FAILED: packing produced overlapping rectangles", overlaps[:5])
        return 1

    # --- geometry buffer -----------------------------------------------------
    buf = array.array("i")
    order = sorted(plotted, key=lambda log: (log.first_year, log.key))
    for log in order:
        buf.extend(
            (
                log.first_year,
                log.last_year,
                row_unified[log.key],
                row_band[log.key],
                GROUP_ORDER.index(group_of(log)),
                site_idx[log.site],
            )
        )
    bin_path = os.path.join(web_data, "logs.bin")
    bin_raw, bin_br = compress.write(bin_path, buf.tobytes())

    # --- metadata ------------------------------------------------------------
    by_site: dict[str, corpus.Log] = {}
    for log in plotted:
        by_site.setdefault(log.site, log)

    site_records = []
    for s in sites:
        log = by_site[s]
        site_records.append(
            {
                "code": s.upper(),
                "site": log.site_name or log.site.upper(),
                "location": log.location,
                "species": log.species_code,
                "latin": log.species_name,
                "common": log.common_name,
                "genus": log.genus,
                "lat": log.lat,
                "lon": log.lon,
                "elev": log.elevation,
                "who": log.investigators,
                "study": log.study_name,
                "doi": log.doi,
                "url": log.url,
                "dating": log.dating,
                "variant": corpus.VARIANT_LABEL.get(log.variant, log.variant),
            }
        )

    index = {
        "fields": FIELDS,
        "n_logs": len(order),
        "groups": GROUP_ORDER,
        "band_heights": [heights.get(g, 0) for g in GROUP_ORDER],
        "unified_rows": pack.row_count(unified),
        "series_ids": [log.series_id for log in order],
        "sites": site_records,
        "year_min": min(log.first_year for log in order),
        "year_max": max(log.last_year for log in order),
        "stats": {
            "files_listed": stats.n_files_listed,
            "files_used": stats.n_files_used,
            "files_skipped_noaa": stats.n_files_skipped_noaa,
            "files_skipped_variant": stats.n_files_skipped_variant,
            "logs_total": len(logs),
            "logs_plotted": len(order),
            "logs_floating": len(floating),
            "logs_disputed": len(disputed),
            "n_sites": len(sites),
            "warnings": len(stats.warnings),
        },
    }
    index_path = os.path.join(web_data, "index.json")
    index_raw, index_br = compress.write(
        index_path, json.dumps(index, separators=(",", ":")).encode()
    )

    # --- ring widths, sharded by site ---------------------------------------
    shards: dict[str, dict[str, list]] = {}
    for log in plotted:
        shards.setdefault(log.site, {})[log.series_id] = {
            "f": log.first_year,
            "v": log.values,
        }
    for site, payload in shards.items():
        with open(os.path.join(web_data, "values", f"{site}.json"), "w") as fh:
            json.dump(payload, fh, separators=(",", ":"))

    print(f"\nwrote {web_data}")
    print(f"  logs.bin    {bin_br / 1e6:.2f} MB br  ({bin_raw / 1e6:.2f} MB raw,"
          f" {bin_raw / bin_br:.2f}x)")
    print(f"  index.json  {index_br / 1e6:.2f} MB br  ({index_raw / 1e6:.2f} MB raw,"
          f" {index_raw / index_br:.2f}x)")
    print(f"  values/     {len(shards)} shards, uncompressed")
    print(f"  first paint {(bin_br + index_br) / 1e6:.2f} MB over the wire")
    return 0


if __name__ == "__main__":
    sys.exit(main())
