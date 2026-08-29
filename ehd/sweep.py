"""Find study records whose declared age range disagrees with their .rwl data.

NCEI's data manager asked for this directly, after accepting the three defects
we reported in August 2026:

    "The time ranges for the ITRDB studies should match the range of dates in
    the rwl file. [...] Please let us know if you find any other studies whose
    age ranges do not match the rwl file age ranges."

So the test is simple - measured span against declared span - and everything
hard about this module is about not sending a wrong list:

* **The declared span must be live, not cached.**  Records are being edited as
  we correspond, so every row is re-checked against the study API by id
  immediately before the report is written, independently of the bulk harvest.
* **Two collections must never be "fixed".**  Seven of the disjoint files are
  the floating Late Glacial collections, whose year column is ring ordinals and
  whose *study record holds the only absolute anchor* - swit195 declares -12287.
  Making the record match the file would destroy the placement.  They are
  reported as do-not-touch, not as defects.
* **The corpus enumeration truncates.**  The study API's own
  ``Continent>Europe`` filter omits genuine European studies, so a file with no
  joined record may still have one.  Those are resolved by id from the file's
  own template header before anything is called uncovered.

Usage:
    python -m ehd.sweep                 # summary table only
    python -m ehd.sweep --csv out.csv   # ... and write the per-file rows
    python -m ehd.sweep --no-verify     # skip the live per-study re-check
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import config, fetch
from .corpus import (
    CorpusStats,
    classify_dating,
    declared_span_ce,
    read_noaa_header,
    read_template_header,
    select_files,
    split_site_variant,
)
from .rwl import parse_rwl

# Plausible calendar years for the archive.  Used only to reject garbage when
# reading the legacy Tucson header, whose layout is not reliably parseable.
YEAR_MIN, YEAR_MAX = -14000, 2100

STUDY_ID_RE = re.compile(r"/(?:paleo/)?study/(\d+)")


@dataclass
class Row:
    """One deduplicated .rwl file, compared against its study record."""

    filename: str
    site: str
    study_id: str = ""
    study_code: str = ""
    study_name: str = ""
    measured: tuple[int, int] | None = None
    declared: tuple[int, int] | None = None
    verified: tuple[int, int] | None = None  # re-read live, by study id
    template: tuple[int, int] | None = None  # *-rwl-noaa.txt header
    header: tuple[int, int] | None = None  # the .rwl's own line 2
    n_series: int = 0
    cls: str = "no record span"
    floating: bool = False  # year column is ring ordinals - do not "correct"
    explained_by: str = ""  # a sibling file the declared span does describe
    note: str = ""

    @property
    def start_delta(self) -> int | None:
        if not (self.measured and self.declared):
            return None
        return self.declared[0] - self.measured[0]

    @property
    def end_delta(self) -> int | None:
        if not (self.measured and self.declared):
            return None
        return self.declared[1] - self.measured[1]

    @property
    def worst_delta(self) -> int:
        a, b = self.start_delta, self.end_delta
        return max(abs(a or 0), abs(b or 0))


def classify_span(measured: tuple[int, int], declared: tuple[int, int]) -> str:
    """How a declared span relates to the data it is supposed to describe."""
    if declared == measured:
        return "exact"
    if declared[1] < measured[0] or measured[1] < declared[0]:
        return "disjoint"
    if declared[0] >= measured[0] and declared[1] <= measured[1]:
        return "declared narrower"
    if declared[0] <= measured[0] and declared[1] >= measured[1]:
        return "declared wider"
    return "declared offset"


def header_span(path: str) -> tuple[int, int] | None:
    """The span written into the legacy Tucson header's second line.

    Advisory only.  ``corpus.py`` declines to parse this header because its
    layout varies too much between files to trust; here we take the last two
    whitespace-separated tokens of line 2 and accept them only if both are
    plausible years in order.  Anything else reads as unknown, never as a
    mismatch, so a parse failure cannot manufacture a defect to report.
    """
    try:
        with open(path, "rb") as fh:
            lines = fh.read(4000).decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if len(lines) < 2:
        return None
    parts = lines[1].split()
    if len(parts) < 2:
        return None
    try:
        first, last = int(parts[-2]), int(parts[-1])
    except ValueError:
        return None
    if not (YEAR_MIN <= first <= last <= YEAR_MAX):
        return None
    return first, last


def template_span(path: str) -> tuple[int, int] | None:
    """Declared span from one specific template file.

    Deliberately not ``read_template_header``, which merges the two families:
    the report needs to say what the *maintained* template says, since that is
    the file NCEI edits.  Normalisation is the shared one, so a BP declaration
    is read the same way here as in the pipeline.
    """
    return declared_span_ce(read_noaa_header(path))


def study_id_from_files(raw_dir: str, site: str) -> str:
    """Recover a study id from a file's own template header.

    This is the escape hatch for the API's unreliable continent filter: the
    template names its study's landing page, so a study the filter hid is still
    reachable by id.
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


def fetch_study_span(study_id: str) -> tuple[int, int] | None:
    """Read one study's declared span live, by id, bypassing the search filter."""
    url = (
        config.NCEI_SEARCH
        + "?"
        + urllib.parse.urlencode({"NOAAStudyId": study_id})
    )
    try:
        doc = json.loads(fetch._get(url, timeout=120))
    except Exception:
        return None
    for study in doc.get("study") or []:
        first, last = study.get("earliestYearCE"), study.get("mostRecentYearCE")
        if first is not None and last is not None:
            return int(first), int(last)
    return None


def is_floating(series, path: str, declared: tuple[int, int] | None) -> bool:
    """Whether the pipeline reads this file's year column as ring ordinals.

    Delegated to ``corpus.classify_dating`` so the sweep and the visualisation
    cannot disagree about which collections are floating - a disagreement here
    means either drawing a Late Glacial pine in the Roman period or asking NCEI
    to delete its only calendar anchor.
    """
    if not series:
        return False
    meta = read_template_header(path)
    if "declared_first" not in meta and declared is not None:
        meta = {"declared_first": declared[0], "declared_last": declared[1]}
    return classify_dating(series, meta) == "floating"


def measured_spans(paths: list[str]) -> dict[str, tuple[int, int]]:
    """Span of every measurement file in the directory, keyed by basename.

    The deduplicated corpus keeps one file per site code, but a study's declared
    range may legitimately describe one of the *other* files it owns - the
    earlywood or maximum-density variant measured on the same trees.  Comparing
    only against the representative reports those as defects.  See
    ``explain_by_sibling``.
    """
    spans: dict[str, tuple[int, int]] = {}
    for path in paths:
        name = os.path.basename(path)
        if name.endswith("-noaa.rwl"):
            continue
        result = parse_rwl(path)
        if result.series:
            spans[name] = (
                min(s.first_year for s in result.series),
                max(s.last_year for s in result.series),
            )
    return spans


def explain_by_sibling(
    row: Row,
    spans: dict[str, tuple[int, int]],
    siblings: dict[str, list[str]],
) -> str:
    """Name a file of the same study whose span the declared range does match.

    NORW011 declares 1550-1997.  ``norw011.rwl`` measures 1409-1997, so the
    dedup representative disagrees - but ``norw011e.rwl`` and ``norw011l.rwl``,
    the earlywood and latewood files of the same study, measure exactly
    1550-1997.  The record is describing them.  Reporting it would be wrong, and
    seven rows in the first draft of this sweep were exactly this.

    The union is accepted too: ESP099 declares 1209-2015, which is no single
    file but is precisely the extent of its two.
    """
    if row.declared is None:
        return ""
    family = [n for n in siblings.get(row.site, []) if n in spans]
    for name in family:
        if name != row.filename and spans[name] == row.declared:
            return name
    if len(family) > 1:
        union = (min(spans[n][0] for n in family), max(spans[n][1] for n in family))
        if union == row.declared:
            return "union of " + ", ".join(sorted(family))
    return ""


def build_rows(raw_dir: str | None = None) -> list[Row]:
    """One row per deduplicated .rwl file, with every span we can find for it."""
    raw_dir = raw_dir or config.path(config.RAW, "itrdb", "europe")
    meta_path = os.path.join(config.path(config.INTERIM), "study_metadata.json")
    by_file = json.load(open(meta_path)).get("by_file", {})

    paths = sorted(glob.glob(os.path.join(raw_dir, "*.rwl")))
    chosen = select_files(paths, CorpusStats())
    spans = measured_spans(paths)

    # Every measurement file grouped by the site code it belongs to, so a
    # declared span can be checked against the whole family and not just the one
    # file dedup happened to keep.
    siblings: dict[str, list[str]] = {}
    for name in spans:
        split = split_site_variant(name)
        siblings.setdefault(split[0] if split else name[:-4], []).append(name)

    rows: list[Row] = []
    for site in sorted(chosen):
        path = chosen[site]
        name = os.path.basename(path)
        api = by_file.get(name) or {}
        row = Row(
            filename=name,
            site=site,
            study_id=str(api.get("study_id") or ""),
            study_code=api.get("study_code") or "",
            study_name=api.get("study_name") or "",
        )
        result = parse_rwl(path)
        if result.series:
            row.n_series = len(result.series)
            row.measured = (
                min(s.first_year for s in result.series),
                max(s.last_year for s in result.series),
            )
        else:
            row.note = "no series parsed"

        first, last = api.get("earliest_year"), api.get("recent_year")
        if first is not None and last is not None:
            row.declared = (int(first), int(last))

        stem = name[: -len(".rwl")]
        row.template = template_span(os.path.join(raw_dir, stem + "-rwl-noaa.txt"))
        row.header = header_span(path)

        if row.measured and row.declared:
            row.cls = classify_span(row.measured, row.declared)
        row.floating = is_floating(result.series, path, row.declared)
        if row.cls not in ("exact", "no record span") and not row.floating:
            row.explained_by = explain_by_sibling(row, spans, siblings)
        rows.append(row)
    return rows


def resolve_missing(rows: list[Row], raw_dir: str) -> int:
    """Fill in records the continent filter hid, by looking them up by id.

    Returns how many rows this rescued.  Anything still without a span after
    this is a genuine gap and is reported as one.
    """
    rescued = 0
    targets = [r for r in rows if r.declared is None and r.measured]
    for row in targets:
        if not row.study_id:
            row.study_id = study_id_from_files(raw_dir, row.site)
        if not row.study_id:
            row.note = "no study id in any header"
            continue
        span = fetch_study_span(row.study_id)
        if span is None:
            row.note = f"study {row.study_id} has no declared span"
            continue
        row.declared = span
        row.cls = classify_span(row.measured, span)
        row.floating = is_floating(
            parse_rwl(os.path.join(raw_dir, row.filename)).series,
            os.path.join(raw_dir, row.filename),
            span,
        )
        row.note = "record found by id; the continent filter had hidden it"
        rescued += 1
    return rescued


def verify_live(rows: list[Row], workers: int = 4) -> list[Row]:
    """Re-read every flagged row's declared span from the live record.

    The bulk harvest is a snapshot and the records are being edited; a row whose
    live span now matches the data has already been fixed and must not be
    reported again.
    """
    flagged = [r for r in rows
               if r.cls not in ("exact", "no record span")
               and not r.floating
               and r.study_id]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        spans = list(pool.map(lambda r: fetch_study_span(r.study_id), flagged))
    fixed = []
    for row, span in zip(flagged, spans):
        row.verified = span
        if span is None:
            row.note = (row.note + "; " if row.note else "") + "live lookup failed"
            continue
        if span != row.declared:
            row.declared = span
            row.cls = classify_span(row.measured, span) if row.measured else row.cls
            if row.cls == "exact":
                fixed.append(row)
    return fixed


# The collections whose year column is ring ordinals and whose study record
# therefore carries the only absolute anchor there is.  "Make the record match
# the file" is exactly the wrong action for these, and the report has to say so.
#
# This list is a *check*, not the mechanism.  It was written with seven entries
# and was already wrong: fra053-055 are three more, invisible until the corpus
# moved onto the maintained templates, and quarantining by name would have sent
# NCEI a request to destroy their placement.  Membership is decided by the
# pipeline's own classifier; this set only asserts that the ones we know about
# are still being caught, and anything beyond it is reported as a new find.
KNOWN_FLOATING = {"swit195", "swit196", "swit197", "swit198", "swit240",
                  "brit099", "brit100", "fra053", "fra054", "fra055"}

CSV_FIELDS = [
    "study_id", "study_code", "study_name", "filename", "n_series",
    "declared_first", "declared_last", "measured_first", "measured_last",
    "start_delta", "end_delta", "class", "explained_by", "template_first", "template_last",
    "rwl_header_first", "rwl_header_last", "note",
]


def write_csv(rows: list[Row], path: str) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (-r.worst_delta, r.study_code)):
            w.writerow({
                "study_id": r.study_id,
                "study_code": r.study_code,
                "study_name": r.study_name,
                "filename": r.filename,
                "n_series": r.n_series,
                "declared_first": r.declared[0] if r.declared else "",
                "declared_last": r.declared[1] if r.declared else "",
                "measured_first": r.measured[0] if r.measured else "",
                "measured_last": r.measured[1] if r.measured else "",
                "start_delta": r.start_delta if r.start_delta is not None else "",
                "end_delta": r.end_delta if r.end_delta is not None else "",
                "class": r.cls,
                "explained_by": r.explained_by,
                "template_first": r.template[0] if r.template else "",
                "template_last": r.template[1] if r.template else "",
                "rwl_header_first": r.header[0] if r.header else "",
                "rwl_header_last": r.header[1] if r.header else "",
                "note": r.note,
            })


def partition(rows: list[Row]) -> dict[str, list[Row]]:
    """Split the corpus into the groups the report is written around."""
    flagged = [r for r in rows if r.cls not in ("exact", "no record span")]
    return {
        "exact": [r for r in rows if r.cls == "exact"],
        "do_not_touch": [r for r in flagged if r.floating],
        "describes_sibling": [r for r in flagged
                              if not r.floating and r.explained_by],
        "reportable": [r for r in flagged
                       if not r.floating and not r.explained_by],
        # A record that exists but declares no age range at all is its own
        # defect, and a different one from a range that disagrees.
        "no_declared_span": [r for r in rows
                             if r.cls == "no record span" and r.study_id],
        # No record reachable by any route.  A coverage gap, not a defect.
        "unresolved": [r for r in rows
                       if r.cls == "no record span" and not r.study_id],
    }


def summarise(rows: list[Row]) -> None:
    order = ["exact", "declared narrower", "declared wider", "declared offset",
             "disjoint", "no record span"]
    counts = {k: 0 for k in order}
    for r in rows:
        counts[r.cls] = counts.get(r.cls, 0) + 1
    print("\n--- span agreement, deduplicated corpus ---")
    for k in order:
        print(f"  {counts[k]:5d}  {k}")
    print(f"  {sum(counts.values()):5d}  total files")

    part = partition(rows)
    reportable = part["reportable"]
    studies = {r.study_id for r in reportable if r.study_id}
    print(f"\n  reportable files         : {len(reportable)}")
    print(f"  reportable studies       : {len(studies)}")
    print(f"  do-not-touch (floating)  : {len(part['do_not_touch'])} files"
          f"  [{', '.join(sorted(r.site for r in part['do_not_touch']))}]")
    print(f"  describes a sibling file : {len(part['describes_sibling'])}"
          " (not defects)")
    print(f"  record with no age range : {len(part['no_declared_span'])}")
    print(f"  no record by any route   : {len(part['unresolved'])}"
          f"  [{', '.join(sorted(r.site for r in part['unresolved']))}]")

    off_by_one = [r for r in reportable if r.worst_delta == 1]
    sig: dict[tuple[int, int], int] = {}
    for r in off_by_one:
        sig[(r.start_delta, r.end_delta)] = sig.get((r.start_delta, r.end_delta), 0) + 1
    print(f"\n  off by exactly one year  : {len(off_by_one)}")
    for k, v in sorted(sig.items(), key=lambda kv: -kv[1]):
        print(f"      start {k[0]:+d}, end {k[1]:+d} : {v}")
    print(f"  off by 2-10 years        : "
          f"{sum(1 for r in reportable if 2 <= r.worst_delta <= 10)}")
    print(f"  off by 11-100 years      : "
          f"{sum(1 for r in reportable if 11 <= r.worst_delta <= 100)}")
    print(f"  off by >100 years        : "
          f"{sum(1 for r in reportable if r.worst_delta > 100)}")


def self_check(rows: list[Row]) -> list[str]:
    """Assertions that fail loudly rather than let a partial run look complete."""
    problems = []
    by_site = {r.site: r for r in rows}
    floating = {r.site for r in rows if r.floating}

    for site in sorted(KNOWN_FLOATING):
        r = by_site.get(site)
        if r is None:
            problems.append(f"{site}: floating collection absent from the corpus")
        elif not r.floating:
            problems.append(
                f"{site}: known floating collection is no longer classified as "
                f"floating (declared {r.declared}, measured {r.measured}) - it "
                "would be reported as a defect and its anchor destroyed")

    for site in sorted(floating - KNOWN_FLOATING):
        problems.append(
            f"{site}: newly detected as floating and not in KNOWN_FLOATING - "
            "confirm by hand before sending, then add it to the set")

    for site in ("brit101", "neth005", "brit", "fran10"):
        r = by_site.get(site)
        if r is None:
            problems.append(f"{site}: absent from the corpus")
        elif r.cls != "exact":
            problems.append(
                f"{site}: NCEI corrected this in August 2026 but it reads "
                f"{r.cls!r} (declared {r.declared}, measured {r.measured})")

    part = partition(rows)
    total = sum(len(v) for v in part.values())
    if total != len(rows):
        problems.append(
            f"partition covers {total} rows of {len(rows)} - some class is "
            "falling through and would be silently omitted from the report")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", help="write per-file rows here")
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the live per-study re-check (offline / dry runs)")
    ap.add_argument("--no-resolve", action="store_true",
                    help="skip resolving records the continent filter hid")
    args = ap.parse_args(argv)

    raw_dir = config.path(config.RAW, "itrdb", "europe")
    rows = build_rows(raw_dir)
    print(f"deduplicated corpus: {len(rows)} files")

    if not args.no_resolve:
        missing = sum(1 for r in rows if r.declared is None)
        rescued = resolve_missing(rows, raw_dir)
        print(f"records hidden by the continent filter: {rescued} of {missing} "
              f"recovered by direct id lookup")

    if not args.no_verify:
        fixed = verify_live(rows)
        print(f"re-checked flagged studies against live records; "
              f"{len(fixed)} already corrected and dropped")

    summarise(rows)

    problems = self_check(rows)
    print("\n--- self-check ---")
    if problems:
        for p in problems:
            print("  FAIL:", p)
    else:
        print("  ok: floating collections quarantined, "
              "the four corrected studies read exact")

    if args.csv:
        part = partition(rows)
        report = part["reportable"] + part["no_declared_span"]
        write_csv(report, args.csv)
        print(f"\nwrote {args.csv} ({len(report)} rows: "
              f"{len(part['reportable'])} span mismatches, "
              f"{len(part['no_declared_span'])} records with no age range)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
