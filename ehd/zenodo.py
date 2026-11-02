"""Per-tree ring widths deposited on Zenodo under an open licence.

One record so far: Land, Remmele & Küppers 2018, 540 subfossil oaks from the Main
region of Germany, CC BY 4.0.  Unlike PANGAEA's restricted deposits these carry
ring widths, so they are drawn with their curves.  See docs/data-survey.md, 4d.

The file is Tucson, but not ITRDB-style Tucson: it has a ``.tuc`` extension and no
header, and it reuses series IDs across trees, so it is read by
``rwl.parse_tucson_blocks``.  Years are astronomical: the file's -6227 to -4056
matches the record's stated 6228 to 4057 BCE at both ends.

The record states a region, not sites, so all 540 hang off one point at the middle
of the stated box.  The location text says so, because the viewer prints
coordinates to three decimals.

What the file must contain is pinned below.  A mismatch stops the build: this is
one reviewed file, not a stream of them.

Usage:
    python -m ehd.zenodo     # download and check against Zenodo's MD5
"""

from __future__ import annotations

import collections
import hashlib
import os
import re
import sys
import urllib.parse
import urllib.request

from . import config, corpus, fetch
from .rwl import parse_tucson_blocks

RECORD = "1326474"
SITE = f"zenodo-{RECORD}"
FILENAME = "Raw oak tree-ring series Main region Germany LBK.tuc"
MD5 = "9624bb601bf39bac3ce643a3332a5a8d"

# From the deposit: its description, and the file as checked 2026-11-01.
N_SERIES = 540
SPAN = (-6227, -4056)
N_RINGS = 90075


class ZenodoMismatch(Exception):
    """The file on disk is not the one that was reviewed."""


def local_path() -> str:
    return os.path.join(config.path(config.RAW, "zenodo", RECORD), FILENAME)


def md5_of(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


def download() -> str:
    """Fetch the file unless a copy with the right checksum is already there."""
    dest = local_path()
    if os.path.exists(dest) and md5_of(dest) == MD5:
        return dest
    url = (f"https://zenodo.org/api/records/{RECORD}/files/"
           f"{urllib.parse.quote(FILENAME)}/content")
    req = urllib.request.Request(url, headers={"User-Agent": fetch.USER_AGENT})
    with urllib.request.urlopen(req, timeout=fetch.TIMEOUT) as resp:
        blob = resp.read()
    got = hashlib.md5(blob).hexdigest()
    if got != MD5:
        raise ZenodoMismatch(f"{FILENAME}: MD5 {got}, Zenodo states {MD5}")
    part = dest + ".part"
    with open(part, "wb") as fh:
        fh.write(blob)
    os.replace(part, dest)
    return dest


def unique_ids(ids: list[str]) -> list[str]:
    """Readable IDs, one per tree: repeats are numbered in file order.

    ``ALTE`` covers several trees with different widths on overlapping years, so
    an ID here does not name a tree.  The viewer finds a log's ring widths by this
    ID, so each must be unique.  The file's double spaces are collapsed.
    """
    clean = [re.sub(r"\s+", " ", i).strip() for i in ids]
    total = collections.Counter(clean)
    seen: collections.Counter = collections.Counter()
    out = []
    for i in clean:
        seen[i] += 1
        out.append(f"{i} ({seen[i]})" if total[i] > 1 else i)
    return out


def build_logs(itrdb_logs: list | None = None, path: str | None = None):
    """``(logs, report)``.  Raises ZenodoMismatch rather than draw an unreviewed file."""
    path = path or local_path()
    if not os.path.exists(path):
        raise ZenodoMismatch(f"{path} is missing: run `python -m ehd.zenodo`")
    if md5_of(path) != MD5:
        raise ZenodoMismatch(f"{path}: checksum differs from the reviewed file")
    result = parse_tucson_blocks(path)
    if result.warnings:
        raise ZenodoMismatch(f"{FILENAME}: {result.warnings[:3]}")
    series = result.series
    span = (min(s.first_year for s in series), max(s.last_year for s in series))
    rings = sum(s.n_measured for s in series)
    if (len(series), span, rings) != (N_SERIES, SPAN, N_RINGS):
        raise ZenodoMismatch(f"{FILENAME}: {len(series)} series, {span}, {rings} rings")

    if itrdb_logs is not None:
        known = {tuple(log.values) for log in itrdb_logs if log.values}
        dup = [s.series_id for s in series if tuple(s.values) in known]
        if dup:
            raise ZenodoMismatch(f"{FILENAME}: also in ITRDB: {dup[:5]}")

    logs = []
    genus, group = corpus.classify("", "Quercus")
    for s, sid in zip(series, unique_ids([s.series_id for s in series])):
        logs.append(corpus.Log(
            key=f"{SITE}/{sid}",
            site=SITE,
            series_id=sid,
            first_year=s.first_year,
            last_year=s.last_year,
            n_measured=s.n_measured,
            values=s.values,
            variant="",
            precision_mm=s.precision_mm,
            species_name="Quercus spec.",
            common_name="oak",
            genus=genus,
            group=group,
            site_name="Main region, Early Neolithic subfossil oaks",
            location=("Southern Germany. Region only: 49.6-50.2°N, 10.2-11.2°E; "
                      "coordinates are the middle of that box"),
            lat=49.9,
            lon=10.7,
            investigators="Land, Alexander; Remmele, Sabine; Küppers, Manfred",
            study_name=("Tree rings as a proxy for seasonal precipitation variability and "
                        "Early Neolithic settlement dynamics in Bavaria, Germany"),
            dois=["10.5281/zenodo.1326474", "10.1371/journal.pone.0210438"],
            url=f"https://zenodo.org/records/{RECORD}",
            dating="absolute",
            source="Zenodo",
            licence="CC BY 4.0",
            licence_url="https://creativecommons.org/licenses/by/4.0/",
            modified_note=("Reformatted for display. The file repeats series IDs, so "
                           "repeats are numbered here, and double spaces are collapsed."),
        ))
    return logs, {"plotted": len(logs)}


def main(argv: list[str] | None = None) -> int:
    print(download())
    logs, report = build_logs()
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
