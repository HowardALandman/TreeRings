"""Filesystem layout.

Bulk data lives off-repo.  The external drive is preferred but is slow to spin
up and its root is not writable by the user account, so the location is
overridable and falls back to a local, gitignored directory.
"""

from __future__ import annotations

import os

EXTERNAL_ROOT = "/Volumes/Expansion/EHD"
LOCAL_FALLBACK = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def data_root() -> str:
    """Resolve the data root, preferring $EHD_DATA, then the external drive."""
    env = os.environ.get("EHD_DATA")
    if env:
        return env
    if os.path.isdir(EXTERNAL_ROOT) and os.access(EXTERNAL_ROOT, os.W_OK):
        return EXTERNAL_ROOT
    return LOCAL_FALLBACK


def path(*parts: str, create: bool = True) -> str:
    p = os.path.join(data_root(), *parts)
    if create:
        os.makedirs(os.path.dirname(p) if os.path.splitext(p)[1] else p, exist_ok=True)
    return p


RAW = "raw"
INTERIM = "interim"
BUILD = "build"

# ITRDB lives on NOAA NCEI.  The "europe" measurement directory is a curated
# enumeration that we cross-check against the study API, because the API's own
# continent filter is unreliable in both directions.
ITRDB_BASE = "https://www.ncei.noaa.gov/pub/data/paleo/treering/measurements"
ITRDB_EUROPE = f"{ITRDB_BASE}/europe/"
NCEI_SEARCH = "https://www.ncei.noaa.gov/access/paleo-search/study/search.json"

# Bounding box used to decide what counts as European, applied to site
# coordinates ourselves rather than trusting locationName.
EUROPE_BBOX = (34.0, 72.0, -25.0, 45.0)  # lat_min, lat_max, lon_min, lon_max
