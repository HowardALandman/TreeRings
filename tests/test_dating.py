"""Regression tests for the dating classifier.

Every case here is a real collection.  The classifier's job is to separate two
things an earlier version conflated: a file whose year column is ring ordinals
(genuinely floating, must not be drawn on a calendar axis) from a file whose
years are calendar dates but whose *declared* span in the archive is wrong.
The second case outnumbers the first by roughly ten to one, and treating it as
the first silently withheld 2,466 dated logs.
"""

from __future__ import annotations

import pytest

from ehd.corpus import classify_dating
from ehd.rwl import Series


def series(first: int, last: int) -> list[Series]:
    n = last - first + 1
    return [
        Series(
            series_id="X",
            source_file="test.rwl",
            first_year=first,
            last_year=last,
            values=[100] * n,
            precision_mm=0.01,
        )
    ]


def meta(first, last) -> dict:
    return {"declared_first": first, "declared_last": last}


# --- declared span narrower than the data is normal, not evidence of drift ---


@pytest.mark.parametrize(
    "site,parsed,declared",
    [
        # 1,248 silver firs: the whole reason this test file exists.
        ("fran10", (1747, 1988), (1943, 1975)),
        ("germ6", (1376, 1972), (1850, 1973)),
        ("aust003", (1276, 1974), (1789, 1974)),
        ("turk016", (1017, 2006), (1332, 2000)),
        ("fran043", (1324, 2005), (1758, 2004)),
        ("norw011", (1409, 1997), (1550, 1997)),
        # Data narrower than the declared span - the other direction.
        ("swed023", (1107, 1827), (1107, 1978)),
        ("grc055", (715, 1803), (715, 2014)),
        # Declared end looks like a typo for the measured one (276 vs 726).
        ("brit101", (271, 726), (271, 276)),
        # BC years, declared and measured both negative.
        ("turk029", (-1767, -742), (-1767, -905)),
    ],
)
def test_overlapping_spans_are_absolute(site, parsed, declared):
    assert classify_dating(series(*parsed), meta(*declared)) == "absolute", site


# --- the genuinely floating collections ------------------------------------


@pytest.mark.parametrize(
    "site,parsed,declared",
    [
        # Swiss Late Glacial pines: rings numbered from 1, declared 12,287 BC.
        ("swit195", (1, 669), (-12287, -10800)),
        ("swit198", (1, 286), (-12287, -10800)),
        # Same, but the ordinals do not start at 1 - magnitude alone cannot
        # tell this from a calendar-dated collection.
        ("swit240", (53, 1434), (-13050, -12050)),
        # Fenland yew: the only two collections declaring years BP, and the
        # only floating ones whose declared span is inside the Holocene.
        ("brit099", (840, 1252), (5224, 4813)),
        ("brit100", (630, 1082), (4612, 4195)),
    ],
)
def test_relative_numbering_is_floating(site, parsed, declared):
    assert classify_dating(series(*parsed), meta(*declared)) == "floating", site


# --- disjoint, but the archive's metadata is what is wrong ------------------


@pytest.mark.parametrize(
    "site,parsed,declared",
    [
        # Empel: the file plainly runs EMP041 1881..1978 in calendar years;
        # NCEI declares -66..106, exactly 1900 years off.
        ("neth005", (1834, 2006), (-66, 106)),
        # Rostrevor: legacy file holding three site codes, header declares
        # 1750..1975 while every series cross-dates in 812..1458.
        ("brit", (812, 1458), (1750, 1975)),
    ],
)
def test_wrong_metadata_is_disputed_not_floating(site, parsed, declared):
    assert classify_dating(series(*parsed), meta(*declared)) == "disputed", site


# --- degenerate inputs ------------------------------------------------------


def test_no_declared_span_is_unverified():
    assert classify_dating(series(1500, 1900), {}) == "unverified"


def test_no_series_is_unknown():
    assert classify_dating([], meta(1500, 1900)) == "unknown"


def test_bp_ordering_alone_does_not_float_an_overlapping_collection():
    # Declared 5224..4813 BP normalises to -3274..-2863 CE; a file measured
    # there is absolutely dated despite the BP declaration.
    assert classify_dating(series(-3200, -2900), meta(5224, 4813)) == "absolute"
