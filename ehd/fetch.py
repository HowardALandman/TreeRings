"""Download the ITRDB European measurement corpus.

Resumable and polite: existing files are skipped, failures are retried with
backoff, and concurrency is kept low because this is a public research archive.

Usage:
    python -m ehd.fetch             # download everything not already present
    python -m ehd.fetch --templates # ... including the live NOAA template files
    python -m ehd.fetch --refresh   # re-download only what the server has changed
    python -m ehd.fetch --limit 40  # small subset, for developing the pipeline
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import config

USER_AGENT = "EHD-visualizer/0.1 (research; contact via github)"
TIMEOUT = 120  # NCEI can be slow; the external drive is slower still
RETRIES = 4


def _get(url: str, timeout: int = TIMEOUT) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise  # genuinely absent; do not burn retries on it
            last = e
        except Exception as e:  # network flakiness, timeouts
            last = e
        time.sleep(2**attempt)
    raise RuntimeError(f"failed after {RETRIES} attempts: {url}: {last}")


# The listing is an Apache index: one row per file, carrying the name, the
# server-side modification time and the byte size.  Both extra columns matter -
# brit.rwl was edited on 2026-08-19 without changing its length, so a size-only
# staleness check misses it, and a date-only check would miss a same-minute
# rewrite.
_ROW_RE = re.compile(
    r'<td><a href="([^"?/]+)">[^<]*</a></td>\s*'
    r'<td align="right">([^<]*)</td>\s*'
    r'<td align="right">([^<]*)</td>'
)
_HREF_RE = re.compile(r'href="([^"?/]+\.(?:rwl|txt))"')


def list_europe_index() -> dict[str, tuple[str, int]]:
    """``{filename: (server_mtime, size_bytes)}`` from the directory listing.

    The row parser is checked against a plain href scan of the same HTML before
    the result is returned.  A listing whose markup changes would otherwise make
    the row regex match nothing and report an empty archive as a successful run,
    which is the failure mode this whole module is written to avoid.
    """
    html = _get(config.ITRDB_EUROPE).decode("utf-8", errors="replace")
    rows = _ROW_RE.findall(html)
    index = {name: (date.strip(), size.strip()) for name, date, size in rows}
    hrefs = set(_HREF_RE.findall(html))
    missing = hrefs - set(index)
    if missing:
        raise RuntimeError(
            f"directory listing: {len(missing)} of {len(hrefs)} files matched the "
            f"href scan but not the row parser (e.g. {sorted(missing)[:3]}); "
            "the listing markup has probably changed"
        )
    out: dict[str, tuple[str, int]] = {}
    for name, (date, size) in index.items():
        try:
            out[name] = (date, int(size))
        except ValueError:
            out[name] = (date, -1)  # directories and odd rows; size unusable
    return out


def list_europe_files(index: dict[str, tuple[str, int]] | None = None) -> list[str]:
    """Enumerate .rwl filenames from the ITRDB europe directory listing.

    This is one of our two independent enumerations of the corpus; the other
    comes from the study API in harvest.py.  They are reconciled there.
    """
    index = index if index is not None else list_europe_index()
    return sorted(n for n in index if n.endswith(".rwl"))


def list_europe_templates(index: dict[str, tuple[str, int]] | None = None) -> list[str]:
    """The live NOAA-template family, ``*-rwl-noaa.txt``.

    NCEI renamed the templates in February 2023.  The old ``*-noaa.rwl`` family
    is frozen - nothing in it is dated after 2023-01 - while these are current:
    Ed Gille's 2026-08-19 corrections went to ``fran10-rwl-noaa.txt`` and left
    ``fran10-noaa.rwl`` at its 2020 content.  There are also 679 site codes that
    exist only under the new name.
    """
    index = index if index is not None else list_europe_index()
    return sorted(n for n in index if n.endswith("-rwl-noaa.txt"))


def stale_files(names: list[str], dest_dir: str,
                index: dict[str, tuple[str, int]]) -> list[str]:
    """Which of ``names`` the server has changed since we copied them.

    A file is stale if it is absent locally, if its size differs from the
    listing's, or if the listing's timestamp is newer than the local mtime.  The
    listing prints server-local time with no zone; a day of slack absorbs that
    without hiding a real edit, since a local copy is written strictly after the
    server mtime it was fetched from.
    """
    stale = []
    for name in names:
        entry = index.get(name)
        if entry is None:
            continue
        date, size = entry
        path = os.path.join(dest_dir, name)
        if not os.path.exists(path):
            stale.append(name)
            continue
        if size >= 0 and os.path.getsize(path) != size:
            stale.append(name)
            continue
        try:
            listed = time.mktime(time.strptime(date, "%Y-%m-%d %H:%M"))
        except ValueError:
            continue
        if listed > os.path.getmtime(path) + 86400:
            stale.append(name)
    return stale


def _looks_like_html(blob: bytes) -> bool:
    """Detect saved error pages, which otherwise land on disk as fake data."""
    head = blob[:200].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def download_one(name: str, dest_dir: str, force: bool = False) -> tuple[str, str]:
    """Return (name, status) where status is stored | cached | missing | error."""
    dest = os.path.join(dest_dir, name)
    if not force and os.path.exists(dest) and os.path.getsize(dest) > 0:
        return name, "cached"
    try:
        blob = _get(config.ITRDB_EUROPE + name)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return name, "missing"
        return name, f"error: {e}"
    except Exception as e:
        return name, f"error: {e}"

    if _looks_like_html(blob):
        # A 200 response can still be an error page; never cache it as data.
        return name, "error: html error page"

    tmp = dest + ".part"
    with open(tmp, "wb") as fh:
        fh.write(blob)
    os.replace(tmp, dest)  # atomic, so an interrupted run leaves no half files
    return name, "stored"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="download at most N files")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument(
        "--templates",
        action="store_true",
        help="fetch the live NOAA template family (*-rwl-noaa.txt) as well",
    )
    ap.add_argument(
        "--refresh",
        action="store_true",
        help="re-download files the server has changed since we copied them",
    )
    args = ap.parse_args(argv)

    dest_dir = config.path(config.RAW, "itrdb", "europe")
    os.makedirs(dest_dir, exist_ok=True)

    index = list_europe_index()
    names = list_europe_files(index)
    print(f"ITRDB europe directory lists {len(names)} .rwl files")
    if args.templates:
        templates = list_europe_templates(index)
        print(f"  plus {len(templates)} live NOAA templates (*-rwl-noaa.txt)")
        names += templates

    force = False
    if args.refresh:
        # Re-check every file we already hold, not just the ones we are about to
        # download: the point is to catch server-side edits, and an edit that
        # keeps the byte count (brit.rwl, 2026-08-19) is invisible to the
        # "already present" test that normally skips them.
        stale = stale_files(names, dest_dir, index)
        print(f"  {len(stale)} file(s) changed on the server since our copy")
        for n in stale[:20]:
            print("    ", n)
        names = stale
        force = True

    if args.limit:
        names = names[: args.limit]

    counts: dict[str, int] = {}
    errors: list[str] = []
    done = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download_one, n, dest_dir, force): n for n in names}
        for fut in as_completed(futures):
            name, status = fut.result()
            key = status.split(":")[0]
            counts[key] = counts.get(key, 0) + 1
            if key == "error":
                errors.append(f"{name}: {status}")
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(names)} ...", flush=True)

    print(f"\ndestination: {dest_dir}")
    for k in sorted(counts):
        print(f"  {k:8} {counts[k]}")
    # Failures are reported, never swallowed: a silently short corpus would
    # look exactly like a complete one in the final visualization.
    if errors:
        print(f"\n{len(errors)} error(s):")
        for e in errors[:20]:
            print("   ", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
