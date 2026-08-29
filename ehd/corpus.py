"""Assemble the deduplicated log corpus with metadata attached.

Three separate duplication traps live in the ITRDB directory, and each one
inflates the log count if ignored:

1. ``foo-noaa.rwl`` is the NOAA-template re-encoding of ``foo.rwl``.  2397 of
   the 2411 such files have a legacy twin holding the same data.
2. A site code carries per-variable variants - ``brit048w`` (ring width),
   ``brit048e`` (earlywood), ``brit048x`` (maximum density) - all measured on
   the *same physical trees*, with the same series IDs and identical spans.
   Left alone these triple some sites: 1151 of 3212 legacy files are variants.
3. Series IDs repeat across sites, so they are only unique when qualified by
   their site code.

We therefore keep one file per site code, preferring total ring width, and key
every log on ``site/series_id``.

Metadata is merged from the NOAA-template headers (structured and complete),
falling back to the study API.  Two template families exist and only
``*-rwl-noaa.txt`` is maintained - see ``read_template_header``.  The legacy
Tucson header is a last resort: its layout varies so much between files that
parsing it reliably is not worth it.
"""

from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass, field

from . import config
from .rwl import Series, parse_rwl

# Site codes always end in digits; anything after that is a variable suffix.
SITE_RE = re.compile(r"^([a-z]+\d+)([a-z]*)$")

# Preference order when a site offers several measured variables.  Widths come
# before densities because a width file is the canonical ring-width record; the
# span is identical either way, so this only affects which values we show.
VARIANT_PREFERENCE = ["", "w", "e", "l", "t", "i", "p", "n", "x"]

VARIANT_LABEL = {
    "": "total ring width",
    "w": "ring width",
    "e": "earlywood width",
    "l": "latewood width",
    "t": "latewood percent",
    "i": "earlywood density",
    "p": "latewood density",
    "n": "minimum density",
    "x": "maximum density",
}

# Genus from the first two letters of the ITRDB 4-letter species code.
GENUS = {
    "QU": ("Quercus", "oak"),
    "PI": ("Pinus", "pine"),
    "PC": ("Picea", "spruce"),
    "AB": ("Abies", "fir"),
    "LA": ("Larix", "larch"),
    "FA": ("Fagus", "beech"),
    "JU": ("Juniperus", "juniper"),
    "PS": ("Pseudotsuga", "douglas-fir"),
    "TS": ("Tsuga", "hemlock"),
    "CD": ("Cedrus", "cedar"),
    "BE": ("Betula", "birch"),
    "FR": ("Fraxinus", "ash"),
    "CA": ("Castanea", "chestnut"),
    "AC": ("Acer", "maple"),
    "AL": ("Alnus", "alder"),
    "PO": ("Populus", "poplar"),
    "SA": ("Salix", "willow"),
    "TA": ("Taxus", "yew"),
    "UL": ("Ulmus", "elm"),
    "CU": ("Cupressus", "cypress"),
    "JG": ("Juglans", "walnut"),
    "TI": ("Tilia", "lime"),
    "SO": ("Sorbus", "rowan"),
    "CR": ("Crataegus", "hawthorn"),
    "OL": ("Olea", "olive"),
    "PT": ("Platanus", "plane"),
}

# Taxa called out by name in the visualization; everything else is grouped.
FOCUS_GROUPS = {"oak", "pine"}


@dataclass
class Log:
    """One physical log, ready to draw."""

    key: str  # site/series_id - unique across the corpus
    site: str
    series_id: str
    first_year: int
    last_year: int
    n_measured: int
    values: list[int | None]
    variant: str
    # metadata, best-effort
    species_code: str = ""
    species_name: str = ""
    common_name: str = ""
    genus: str = ""
    group: str = "other"
    site_name: str = ""
    location: str = ""
    lat: float | None = None
    lon: float | None = None
    elevation: str = ""
    investigators: str = ""
    study_name: str = ""
    doi: str = ""
    url: str = ""
    dating: str = "absolute"

    @property
    def n_rings(self) -> int:
        return self.last_year - self.first_year + 1


@dataclass
class CorpusStats:
    n_files_listed: int = 0
    n_files_used: int = 0
    n_files_skipped_noaa: int = 0
    n_files_skipped_variant: int = 0
    n_files_unmatched: int = 0
    n_files_empty: int = 0
    n_logs: int = 0
    n_floating: int = 0
    n_disputed: int = 0
    warnings: list[str] = field(default_factory=list)


def split_site_variant(filename: str) -> tuple[str, str] | None:
    """``brit048w.rwl`` -> ``('brit048', 'w')``.  None if it does not fit."""
    stem = os.path.basename(filename)
    if stem.endswith(".rwl"):
        stem = stem[: -len(".rwl")]
    if stem.endswith("-noaa"):
        stem = stem[: -len("-noaa")]
    m = SITE_RE.match(stem)
    if not m:
        return None
    return m.group(1), m.group(2)


def select_files(paths: list[str], stats: CorpusStats) -> dict[str, str]:
    """Choose one file per site code.  Returns ``{site_code: path}``."""
    best: dict[str, tuple[int, str]] = {}
    for p in paths:
        name = os.path.basename(p)
        if name.endswith("-noaa.rwl"):
            stats.n_files_skipped_noaa += 1
            continue
        split = split_site_variant(name)
        if split is None:
            # Hand-named oddities such as germ14_corrected.rwl. Keyed on their
            # own stem so they are kept rather than quietly dropped.
            stats.n_files_unmatched += 1
            best.setdefault(name[:-4], (len(VARIANT_PREFERENCE), p))
            continue
        site, variant = split
        try:
            rank = VARIANT_PREFERENCE.index(variant)
        except ValueError:
            rank = len(VARIANT_PREFERENCE)
        prev = best.get(site)
        if prev is None or rank < prev[0]:
            best[site] = (rank, p)

    chosen = {site: p for site, (_, p) in best.items()}
    stats.n_files_skipped_variant = (
        len(paths) - stats.n_files_skipped_noaa - len(chosen) - 0
    )
    return chosen


# Two template generations, two vocabularies for the same facts.  The v2 files
# (``*-noaa.rwl``, frozen since 2023) say Earliest_Year / Most_Recent_Year /
# Elevation / Online_Resource; the v3 files (``*-rwl-noaa.txt``, current) say
# First_Year / Last_Year / Elevation_m / NOAA_Landing_Page.  Reading only the v2
# names against a v3 file yields a header with no declared span at all, which
# reads downstream as "unverifiable" rather than as an error - so both
# vocabularies are mapped rather than one being migrated to the other.
NOAA_FIELDS = {
    "Study_Name": "study_name",
    "Investigators": "investigators",
    "DOI": "doi",
    "Site_Name": "site_name",
    "Location": "location",
    "Northernmost_Latitude": "lat",
    "Easternmost_Longitude": "lon",
    "Elevation": "elevation",
    "Elevation_m": "elevation",
    "Species_Name": "species_name",
    "Common_Name": "common_name",
    "Online_Resource": "url",
    "NOAA_Landing_Page": "url",
    "Earliest_Year": "declared_first",
    "Most_Recent_Year": "declared_last",
    "First_Year": "declared_first",
    "Last_Year": "declared_last",
}

# How far the data may sit outside the declared span before the two are judged
# disjoint.  Declared years are often rounded to the nearest decade.
DATING_TOLERANCE_YEARS = 100

# The oldest absolutely dated collection the archive declares is swed334, at
# 5407 BC.  A declared start older than this horizon marks subfossil material
# whose calendar position, if it has one, was established outside the file - so
# the file's own year column cannot be read as a calendar date.  -8000 leaves
# ~2,600 years of margin below the oldest dated collection and ~4,300 years
# above the Late Glacial declarations (swit195-198 at -12287, swit240 at
# -13050) that the horizon exists to catch.
PRE_ARCHIVE_HORIZON_CE = -8000


def read_noaa_header(path: str) -> dict:
    """Parse the ``#``-commented NOAA template header for metadata."""
    out: dict = {}
    try:
        with open(path, "rb") as fh:
            blob = fh.read(20000)
    except OSError:
        return out
    for raw in blob.decode("utf-8", errors="replace").splitlines():
        if not raw.startswith("#"):
            continue
        line = raw.lstrip("#").strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        field_name = NOAA_FIELDS.get(key.strip())
        if not field_name or not value.strip():
            continue
        out.setdefault(field_name, value.strip())
    for k in ("lat", "lon"):
        if k in out:
            try:
                out[k] = float(out[k])
            except ValueError:
                out.pop(k)
    return out


def read_template_header(rwl_path: str) -> dict:
    """Metadata from the NOAA template sibling, preferring the maintained one.

    There are two template families in the archive and only one of them is
    alive.  NCEI renamed the templates to ``<site>-rwl-noaa.txt`` in February
    2023 and stopped touching ``<site>-noaa.rwl``: the old family has 2,411
    files, none dated after 2023-01, while the new one has 3,077 dated through
    2026-08.  The August 2026 corrections went to ``fran10-rwl-noaa.txt`` and
    left ``fran10-noaa.rwl`` at its 2020 content, so reading the old name meant
    reading a three-year-old snapshot of a record that had since been fixed.
    679 site codes exist only under the new name; 13 only under the old, which
    is why the old one is still read as a fallback rather than dropped.

    Descriptive fields merge, live winning.  The declared span does *not*: it is
    taken whole from one source or the other, because a first year from the 2020
    file paired with a last year from the 2026 file would be a span that has
    never described anything.
    """
    stem = rwl_path[: -len(".rwl")] if rwl_path.endswith(".rwl") else rwl_path
    legacy = read_noaa_header(stem + "-noaa.rwl")
    live = read_noaa_header(stem + "-rwl-noaa.txt")
    meta = {**legacy, **live}
    for source in (live, legacy):
        if "declared_first" in source and "declared_last" in source:
            meta["declared_first"] = source["declared_first"]
            meta["declared_last"] = source["declared_last"]
            break
    else:
        meta.pop("declared_first", None)
        meta.pop("declared_last", None)
    return meta


def species_from_study_name(name: str) -> str:
    """ITRDB study names embed the species code: '... - QURO - ITRDB GERM001'."""
    m = re.search(r" - ([A-Z]{4}) - ITRDB", name or "")
    return m.group(1) if m else ""


def classify(species_code: str) -> tuple[str, str]:
    """Return (genus, display group) for a 4-letter ITRDB species code."""
    genus, common = GENUS.get((species_code or "")[:2].upper(), ("", ""))
    if common in FOCUS_GROUPS:
        return genus, common
    return genus, common or "other"


def build_logs(raw_dir: str | None = None, limit: int = 0):
    """Parse the corpus into deduplicated Log records with metadata attached."""
    raw_dir = raw_dir or config.path(config.RAW, "itrdb", "europe")
    stats = CorpusStats()

    paths = sorted(glob.glob(os.path.join(raw_dir, "*.rwl")))
    stats.n_files_listed = len(paths)
    chosen = select_files(paths, stats)

    api_meta: dict[str, dict] = {}
    meta_path = os.path.join(config.path(config.INTERIM), "study_metadata.json")
    if os.path.exists(meta_path):
        api_meta = json.load(open(meta_path)).get("by_file", {})

    logs: list[Log] = []
    for site in sorted(chosen) if not limit else sorted(chosen)[:limit]:
        path = chosen[site]
        name = os.path.basename(path)
        result = parse_rwl(path)
        if not result.series:
            stats.n_files_empty += 1
            stats.warnings.append(f"{name}: no series parsed")
            continue
        stats.n_files_used += 1
        stats.warnings.extend(result.warnings)

        # Prefer the NOAA-template sibling's header; fall back to the API.
        meta = read_template_header(path)
        api = api_meta.get(name) or {}
        # Not every file has a NOAA-template sibling, so fall back to the study
        # API for the declared span; without one, dating is unverifiable.
        if "declared_first" not in meta and api.get("earliest_year") is not None:
            meta = dict(meta)
            meta["declared_first"] = api.get("earliest_year")
            meta["declared_last"] = api.get("recent_year")
        study_name = meta.get("study_name") or api.get("study_name") or ""
        code = species_from_study_name(study_name)
        genus, group = classify(code)

        variant = (split_site_variant(name) or (site, ""))[1]
        dating = classify_dating(result.series, meta)

        for s in result.series:
            logs.append(
                Log(
                    key=f"{site}/{s.series_id}",
                    site=site,
                    series_id=s.series_id,
                    first_year=s.first_year,
                    last_year=s.last_year,
                    n_measured=s.n_measured,
                    values=s.values,
                    variant=variant,
                    species_code=code,
                    species_name=meta.get("species_name", ""),
                    common_name=meta.get("common_name", ""),
                    genus=genus,
                    group=group,
                    site_name=meta.get("site_name") or api.get("site_name") or "",
                    location=meta.get("location") or api.get("location") or "",
                    lat=meta.get("lat", api.get("lat")),
                    lon=meta.get("lon", api.get("lon")),
                    elevation=str(meta.get("elevation", "")),
                    investigators=meta.get("investigators")
                    or api.get("investigators")
                    or "",
                    study_name=study_name,
                    doi=meta.get("doi") or (api.get("doi") or ""),
                    url=meta.get("url") or (api.get("url") or ""),
                    dating=dating,
                )
            )
        if dating == "floating":
            stats.n_floating += 1
        elif dating == "disputed":
            stats.n_disputed += 1
            stats.warnings.append(
                f"{name}: declared span {declared_span_ce(meta)} does not meet "
                f"measured span "
                f"({min(s.first_year for s in result.series)}, "
                f"{max(s.last_year for s in result.series)})"
            )

    stats.n_logs = len(logs)
    return logs, stats


def declared_span_ce(meta: dict) -> tuple[int, int] | None:
    """Read the declared span from a NOAA header, normalising BP to CE.

    The header's units are not consistent across the archive: Late Glacial
    studies declare years BP while the rest declare CE.  The reliable tell is
    ordering - BP counts backwards, so ``Earliest_Year > Most_Recent_Year``
    means the pair is BP (swit240 declares 15000..14000 BP = -13050..-12050 CE).
    """
    try:
        first = int(float(meta["declared_first"]))
        last = int(float(meta["declared_last"]))
    except (KeyError, TypeError, ValueError):
        return None
    if first > last:
        return 1950 - first, 1950 - last
    return first, last


def declares_years_bp(meta: dict) -> bool:
    """True when the declared span is written in years BP, which count backwards.

    Ten collections in the European corpus do this: the Fenland yews (brit099,
    brit100), the Swiss Late Glacial pines (swit195-198, swit240) and the French
    Late Glacial pines (fra053-055).  The mark is the archive's own, not a guess
    from magnitude, so it is read directly rather than inferred.

    Ordering is the mechanism because nothing better is machine-readable, but it
    is not the *evidence*.  Two independent sources settle the convention, and
    both say BP rather than BC:

    * the depositors say so in the file - brit099's ``Description`` reads "the
      TRW series are in index years and have to be converted to cal. years BP
      with the earliest year being 5224 +/-4 cal. years BP", and brit100 the
      same with 4612;
    * NCEI performs the conversion itself for eight of the ten, and it is
      exactly this one: ``earliestYearCE`` equals ``1950 - First_Year`` for
      swit195-198, swit240 and fra053-055.

    The two it does *not* convert are brit099 and brit100, whose
    ``earliestYearCE`` reads 5224 and 4612 - dates in the future.  Reported to
    NCEI 2026-08-28.

    The explicit ``Time_Unit`` field cannot substitute for the ordering test:
    brit099 and brit100 say ``CE`` while carrying BP values, and the seven Late
    Glacial collections leave it empty.
    """
    try:
        return int(float(meta["declared_first"])) > int(float(meta["declared_last"]))
    except (KeyError, TypeError, ValueError):
        return False


def spans_overlap(
    a: tuple[int, int], b: tuple[int, int], slack: int = DATING_TOLERANCE_YEARS
) -> bool:
    """True when two closed year intervals intersect, allowing ``slack`` at each end."""
    return a[0] <= b[1] + slack and b[0] <= a[1] + slack


def classify_dating(series: list[Series], meta: dict) -> str:
    """Decide what a collection's year column means.

    ``absolute``    the measured span and the declared span describe the same
                    interval, so the years are calendar dates.
    ``floating``    the year column is ring ordinals carrying no calendar
                    position.  Drawing these on the time axis would put a
                    13,000 BC pine in the Roman period.
    ``disputed``    the two spans are disjoint, yet nothing marks the file as
                    subfossil: the years still read as calendar dates and it is
                    the archive's declared span that is wrong.  Plotted, and
                    recorded as a warning for reporting upstream.
    ``unverified``  no declared span to check against.
    ``unknown``     no series.

    An earlier version returned ``floating`` for *any* disagreement with the
    declared span.  That conflated "the rings are numbered from 1" with "NCEI's
    metadata is wrong", and the second case is much the more common: it
    withheld 1,248 calendar-dated silver firs (fran10, declared 1943-1975,
    measured 1747-1988) alongside the 136 genuinely floating Late Glacial logs.
    Overlap replaces endpoint agreement because a declared span is routinely
    narrower than the data - it describes the site chronology, not the longest
    log - and being narrower is not evidence of relative numbering.
    """
    if not series:
        return "unknown"
    declared = declared_span_ce(meta)
    if declared is None:
        return "unverified"
    parsed = (min(s.first_year for s in series), max(s.last_year for s in series))
    if spans_overlap(parsed, declared):
        return "absolute"
    # Disjoint: either the file is relative-numbered or the metadata is wrong.
    # Two marks, both made by the archive rather than inferred from the data,
    # say "subfossil, dated outside the file": a span declared in years BP, and
    # a declared start older than any absolutely dated material in the archive.
    if declares_years_bp(meta) or declared[0] < PRE_ARCHIVE_HORIZON_CE:
        return "floating"
    return "disputed"
