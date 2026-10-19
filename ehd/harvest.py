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
exactly how much of A that join actually covers.  Files the join misses are
then looked up by the study id written in their own template header.

That second step is not optional.  When NCEI withdraws a study it keeps the
record, notes the removal in ``studyNotes``, and drops the ``.rwl`` from the
record's file list - but leaves the file itself in the directory listing.  A
filename join therefore cannot see a withdrawal at all: the file simply arrives
with no metadata, and its template header carries on describing it as live.
That is how 3,424 logs from 25 withdrawn studies (the Maessen Dutch set, removed
2025-07-31 as "did not meet ITRDB standards", among them) were plotted until
2026-10.

Usage:
    python -m ehd.harvest
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse

from . import config, fetch

PAGE = 2000

STUDY_ID_RE = re.compile(r"/(?:paleo/)?study/(\d+)")

# NCEI's withdrawal mark: a dated line in ``studyNotes``.  Every form seen in
# the European corpus as of 2026-10-02:
#   31-Jul-2025: Removed - Data did not meet ITRDB standards. See Comments ...
#   30-Jul-2025: Study Removed - data was mean curves of GERM016
#   21-Aug-2025: Study Removed - repeat data; study was a resubmission of CHE413
#   10-Dec-2025: RWL file removed due to crossdating issues.
# Anchored on the date so that prose such as "series from five timbers removed
# from the Great Tower" (a real study description) is not read as one.
WITHDRAWAL_RE = re.compile(
    r"^\s*(\d{1,2}-[A-Za-z]{3}-\d{4}):?\s*"
    r"((?:Study\s+|RWL\s+file\s+)?removed\b.*?)\s*$",
    re.I | re.M,
)


def withdrawal(notes: str | None) -> str:
    """NCEI's removal statement from a study's notes, or "" if there is none."""
    m = WITHDRAWAL_RE.search((notes or "").replace("\r", ""))
    return f"{m.group(1)}: {m.group(2)}" if m else ""


def study_id_from_files(raw_dir: str, site: str) -> str:
    """Recover a study id from a file's own template header.

    This is the escape hatch for the API's unreliable continent filter, and for
    withdrawn studies whose record no longer lists the file: the template names
    its study's landing page, so the record is still reachable by id.
    """
    for suffix in ("-rwl-noaa.txt", "-noaa.rwl", ".rwl"):
        path = os.path.join(raw_dir, site + suffix)
        if not os.path.exists(path):
            continue
        try:
            with open(path, "rb") as fh:
                blob = fh.read(20000).decode("utf-8", errors="replace")
        except OSError:
            continue
        m = STUDY_ID_RE.search(blob)
        if m:
            return m.group(1)
    return ""


def fetch_study(study_id: str) -> dict | None:
    """One study record, live, by id.  Raises if the API cannot be reached."""
    url = config.NCEI_SEARCH + "?" + urllib.parse.urlencode({"NOAAStudyId": study_id})
    studies = json.loads(fetch._get(url, timeout=180)).get("study") or []
    return studies[0] if studies else None


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
    dois = publication_dois(pubs)
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
        "dois": dois,
        "citation": citation,
        "url": study.get("onlineResourceLink"),
        "earliest_year": study.get("earliestYearCE"),
        "recent_year": study.get("mostRecentYearCE"),
        "withdrawn": withdrawal(study.get("studyNotes")),
    }


def publication_dois(pubs: list[dict]) -> list[str]:
    """Every DOI a study record lists for its publications, in record order.

    The record keeps them under ``identifier`` ({"type": "doi", "id": ...}).
    This used to read a top-level ``doi`` key that the API never sends, so
    until 2026-10-19 no harvested record had a DOI (0 of 12,629) and every DOI
    the viewer showed came from the per-file template, unchecked.
    """
    out: list[str] = []
    for p in pubs:
        idents = p.get("identifier") or []
        for ident in [idents] if isinstance(idents, dict) else idents:
            if (ident.get("type") or "").lower() != "doi" or not ident.get("id"):
                continue
            doi = ident["id"].strip()
            if doi not in out:
                out.append(doi)
    return out


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

    # Resolve what the join missed by the study id in each file's own template.
    # This is where withdrawn studies are found (see the module docstring), so a
    # lookup that fails aborts the harvest rather than leaving a gap: a missing
    # record here would plot a withdrawn study as if it were live.
    raw_dir = config.path(config.RAW, "itrdb", "europe")
    unlisted: list[str] = []  # record found, but it no longer lists the file
    for name in sorted(corpus - set(by_file)):
        study_id = study_id_from_files(raw_dir, name[: -len(".rwl")])
        if not study_id:
            continue
        study = fetch_study(study_id)
        if study is None:
            continue
        by_file[name] = _fields(study)
        if not by_file[name]["withdrawn"] and name not in _data_files(study):
            unlisted.append(f"{name} (study {study_id})")
    withdrawn = sorted(n for n in corpus if (by_file.get(n) or {}).get("withdrawn"))

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
    print(f"  withdrawn by NCEI          : {len(withdrawn)}")
    for name in withdrawn:
        print(f"      {name}: {by_file[name]['withdrawn']}")
    # The second, independent signal: a live record that has stopped pointing at
    # the file without saying why.  Not acted on - FRA053-055 do this because
    # their study now points at a 2025 re-deposit - but printed for review, so a
    # withdrawal worded in a way WITHDRAWAL_RE does not know cannot pass unseen.
    print(f"  record no longer lists file: {len(unlisted)} (not withdrawn; review)")
    for entry in unlisted:
        print(f"      {entry}")

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
