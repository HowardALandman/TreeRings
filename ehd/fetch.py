"""Download the ITRDB European measurement corpus.

Resumable and polite: existing files are skipped, failures are retried with
backoff, and concurrency is kept low because this is a public research archive.

Usage:
    python -m ehd.fetch            # download everything not already present
    python -m ehd.fetch --limit 40 # small subset, for developing the pipeline
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


def list_europe_files() -> list[str]:
    """Enumerate .rwl filenames from the ITRDB europe directory listing.

    This is one of our two independent enumerations of the corpus; the other
    comes from the study API in harvest.py.  They are reconciled there.
    """
    html = _get(config.ITRDB_EUROPE).decode("utf-8", errors="replace")
    names = re.findall(r'href="([^"?/]+\.rwl)"', html)
    return sorted(set(names))


def _looks_like_html(blob: bytes) -> bool:
    """Detect saved error pages, which otherwise land on disk as fake data."""
    head = blob[:200].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def download_one(name: str, dest_dir: str) -> tuple[str, str]:
    """Return (name, status) where status is stored | cached | missing | error."""
    dest = os.path.join(dest_dir, name)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
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
    args = ap.parse_args(argv)

    dest_dir = config.path(config.RAW, "itrdb", "europe")
    os.makedirs(dest_dir, exist_ok=True)

    names = list_europe_files()
    print(f"ITRDB europe directory lists {len(names)} .rwl files")
    if args.limit:
        names = names[: args.limit]

    counts: dict[str, int] = {}
    errors: list[str] = []
    done = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download_one, n, dest_dir): n for n in names}
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
