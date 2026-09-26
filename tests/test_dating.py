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
        # French Late Glacial pines.  These were invisible to the classifier
        # until 2026-08-28: they have no *-noaa.rwl sibling and no study record
        # the continent filter would return, so nothing declared a span and all
        # 111 logs were plotted at years 1-434 CE.  Their span exists only in
        # the maintained *-rwl-noaa.txt template.
        ("fra053", (1, 434), (-12428, -11995)),
        ("fra054", (1, 348), (-12140, -11793)),
        ("fra055", (1, 233), (-11977, -11745)),
        # Fenland yew: the only floating collections whose declared span is
        # inside the Holocene, so the pre-archive horizon cannot catch them and
        # the BP ordering is the only mark that does.
        ("brit099", (840, 1252), (5224, 4813)),
        ("brit100", (630, 1082), (4612, 4195)),
    ],
)
def test_relative_numbering_is_floating(site, parsed, declared):
    assert classify_dating(series(*parsed), meta(*declared)) == "floating", site


# --- disjoint, but the archive's metadata is what is wrong ------------------
#
# Both records below were corrected by NCEI on 2026-08-21 after we reported
# them, and the live archive no longer declares these spans - the `disputed`
# class is empty as of the 2026-08-28 harvest.  The cases are kept because the
# classifier still has to reach this verdict: a file whose declared span is
# disjoint from its data, with no BP mark and no pre-archive start, is wrong
# metadata rather than relative numbering, and the next such defect must not be
# silently withheld as floating.


@pytest.mark.parametrize(
    "site,parsed,declared",
    [
        # Empel, as the record read before the fix: the file plainly runs
        # EMP041 1881..1978 in calendar years while NCEI declared -66..106,
        # exactly 1900 years off.  Now 1834..2006.
        ("neth005", (1834, 2006), (-66, 106)),
        # Rostrevor, as the record read before the fix: a legacy file holding
        # three site codes, declaring 1750..1975 while every series cross-dates
        # in 812..1458.  Now 812..1458, in the record, the template and the
        # .rwl's own header line 2.
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


def test_raw_bp_template_values_float_the_french_late_glacial():
    """The path the corpus actually takes for fra053, end to end.

    The parametrized cases above hand the classifier a span already normalised
    to CE, which exercises the pre-archive horizon.  This one hands it the
    template's own numbers - 14378 down to 13945, Time_Unit not consulted - so the
    BP inversion has to be recognised first.  Both routes must reach floating,
    because the horizon alone would not survive a Holocene-age BP declaration
    and the inversion alone would not survive a template that spelt the years
    out in CE.
    """
    assert classify_dating(series(1, 434), meta(14378, 13945)) == "floating"
