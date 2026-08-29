"""Harvest study metadata from NOAA NCEI and reconcile it against the corpus.

Two independent enumerations of "the European corpus" exist, and they disagree:

  A. the ITRDB ``measurements/europe/`` directory listing (file-level, curated)
  B. the NCEI study search API (study-level, richer metadata)

Source B's own ``locationName=Continent>Europe`` filter is not trustworthy in
either direction.  As of 2026-08-28 it returns 9,022 study records, of which
6,834 reference a .rwl file, of which only 2,195 have coordinates inside Europe;
and it omits genuine European studies - SWIT240, and the French Late Glacial
pines FRA053-055, whose records have to be recovered by id from the study
numbers written into their own template files.  So we take A as the definition
of the corpus, use B purely for metadata, join the two on filename, and report
exactly how much of A that join actually covers.  ``ehd.sweep`` closes the
remaining gap by resolving what the join misses.

Usage:
    python -m ehd.harvest
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse

from . import config, fetch

PAGE = 2000


def _fields(study: dict) -> dict:
    """Pull the handful of fields worth keeping from a fat study record."""
    site = (study.get("site") or [{}])[0]
    geo = (site.get("geo") or {}).get("geometry") or {}
    coords = geo.get("coordinates") or []
    lat = lon = None
    if len(coords) >= 2:
        try:
            lat, lon = float(coords[0]), float(coords[1])
        except (TypeError, ValueError):
            lat = lon = None

    pubs = study.get("publication") or []
    doi = next((p.get("doi") for p in pubs if p.get("doi")), None)
    citation = next((p.get("citation") for p in pubs if p.get("citation")), None)

    return {
        "study_id": study.get("NOAAStudyId"),
        "study_name": study.get("studyName"),
        "study_code": study.get("studyCode"),
        "site_name": site.get("siteName"),
        "location": site.get("locationName"),
        "lat": lat,
        "lon": lon,
        "investigators": study.get("investigators"),
        "doi": doi,
        "citation": citation,
        "url": study.get("onlineResourceLink"),
        "earliest_year": study.get("earliestYearCE"),
        "recent_year": study.get("mostRecentYearCE"),
    }


def _data_files(study: dict) -> list[str]:
    """Basenames of every data file the study points at."""
    out = []
    for site in study.get("site") or []:
        for pd in site.get("paleoData") or []:
            for f in pd.get("dataFile") or []:
                url = f.get("fileUrl") or ""
                if url:
                    out.append(os.path.basename(urllib.parse.urlparse(url).path))
    return out


def paginate(params: dict) -> list[dict]:
    """Follow the API's own ``next`` links until exhausted."""
    studies: list[dict] = []
    url = config.NCEI_SEARCH + "?" + urllib.parse.urlencode(params)
    seen_pages = 0
    while url:
        blob = fetch._get(url, timeout=180)
        doc = json.loads(blob)
        batch = doc.get("study") or []
        studies.extend(batch)
        seen_pages += 1
        print(f"  page {seen_pages}: +{len(batch)} (total {len(studies)})", flush=True)
        page = (doc.get("page") or [{}])[0]
        url = page.get("next") if len(batch) else None
    return studies


def main(argv: list[str] | None = None) -> int:
    out_dir = config.path(config.INTERIM)
    os.makedirs(out_dir, exist_ok=True)

    print("enumerating ITRDB europe/ directory (source A)...")
    listing = fetch.list_europe_index()
    corpus = set(fetch.list_europe_files(listing))
    print(f"  {len(corpus)} .rwl files")
    # Snapshot the listing's per-file dates and sizes.  This is the baseline
    # `fetch --refresh` compares against, and it is the only record of when the
    # archive last touched a file we hold.
    listing_path = os.path.join(out_dir, "europe_listing.json")
    with open(listing_path, "w") as fh:
        json.dump(listing, fh)
    print(f"  listing snapshot -> {listing_path}")

    print("harvesting NCEI study metadata (source B)...")
    studies = paginate(
        {
            "dataTypeId": 18,
            "locationName": "Continent>Europe",
            "limit": PAGE,
        }
    )
    print(f"  {len(studies)} study records")

    # Join on filename.  One study can back several files (earlywood/latewood
    # variants), and one file belongs to exactly one study.
    by_file: dict[str, dict] = {}
    for study in studies:
        meta = _fields(study)
        for name in _data_files(study):
            if name.endswith(".rwl"):
                by_file[name] = meta

    covered = corpus & set(by_file)
    uncovered = corpus - set(by_file)
    extra = set(by_file) - corpus

    print("\n--- reconciliation ---")
    print(f"  corpus files (A)          : {len(corpus)}")
    print(f"  files with metadata (A n B): {len(covered)}  "
          f"({100 * len(covered) / max(len(corpus), 1):.1f}%)")
    print(f"  corpus files w/o metadata  : {len(uncovered)}")
    print(f"  metadata for non-corpus    : {len(extra)} (non-European studies)")
    if uncovered:
        print("  examples lacking metadata  :", ", ".join(sorted(uncovered)[:10]))

    path = os.path.join(out_dir, "study_metadata.json")
    with open(path, "w") as fh:
        json.dump(
            {
                "corpus_files": sorted(corpus),
                "by_file": by_file,
                "reconciliation": {
                    "n_corpus": len(corpus),
                    "n_covered": len(covered),
                    "n_uncovered": len(uncovered),
                    "uncovered": sorted(uncovered),
                },
            },
            fh,
        )
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
