"""Regression tests for the Tucson .rwl parser.

Every fixture here was chosen because it broke an earlier version of the parser.
They encode the format traps found in the real ITRDB corpus, so a future
"simplification" that reintroduces one of them fails loudly.
"""

from __future__ import annotations

import os

import pytest

from ehd.rwl import parse_rwl

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name: str) -> str:
    return os.path.join(FIXTURES, name)


def parse(name: str):
    return parse_rwl(fixture(name))


def series_by_id(result, series_id: str):
    matches = [s for s in result.series if s.series_id == series_id]
    assert matches, f"series {series_id!r} not found"
    return matches[0]


# --- the four files that a whitespace-splitting parser could not read --------


@pytest.mark.parametrize(
    "name,min_logs",
    [
        ("ital019.rwl", 16),  # ID runs into year: '0003401Q1890'
        ("che419.rwl", 26),  # trailing site name past col 72, -999 gaps
        ("finl049.rwl", 38),  # 8-char ID abutting the year
        ("swed321.rwl", 11),  # 8-char numeric ID abutting the year
    ],
)
def test_fixed_width_files_parse(name, min_logs):
    result = parse(name)
    assert len(result.series) == min_logs
    assert result.warnings == []


def test_id_running_into_year_is_split_correctly():
    """'0003401Q1890' must split as ID '0003401Q' + year 1890, not one token."""
    result = parse("ital019.rwl")
    ids = {s.series_id for s in result.series}
    assert "0003401Q" in ids
    assert all(not s.series_id[-4:].isdigit() or len(s.series_id) == 8 for s in result.series)


# --- BC years, which borrow column 8 for the minus sign ---------------------


@pytest.mark.parametrize(
    "name,first,last",
    [
        # Spans independently confirmed against NOAA NCEI study metadata.
        ("brit036.rwl", -3776, -3016),
        ("brit037.rwl", -2920, -2444),
    ],
)
def test_bc_years_parse_with_correct_sign(name, first, last):
    result = parse(name)
    assert min(s.first_year for s in result.series) == first
    assert max(s.last_year for s in result.series) == last
    assert result.warnings == []


# --- -999 is a missing ring, not a terminator -------------------------------


def test_missing_values_do_not_terminate_a_series():
    """che419's RCS0302a has 20 unmeasured years mid-series, then real data.

    Treating -999 as a terminator truncated this log from 1854-2010 to
    1854-1864 - a 146-year error that would silently shrink the rectangle.
    """
    s = series_by_id(parse("che419.rwl"), "RCS0302a")
    assert (s.first_year, s.last_year) == (1854, 2010)
    assert s.n_rings == 157
    assert s.n_measured == 103
    # The 1870s decade is entirely unmeasured but sits inside the span.
    assert all(v is None for v in s.values[1870 - s.first_year : 1880 - s.first_year])
    # Real data resumes afterwards.
    assert s.values[1895 - s.first_year] == 68


def test_series_ends_are_trimmed_to_real_measurements():
    """A span must start and end on a measured ring, never on a gap."""
    for name in ("che419.rwl", "germ001.rwl", "brit037.rwl"):
        for s in parse(name).series:
            assert s.values[0] is not None
            assert s.values[-1] is not None
            assert len(s.values) == s.n_rings


# --- structural invariants that must hold for every log ---------------------


@pytest.mark.parametrize(
    "name",
    [
        "brit036.rwl",
        "brit037.rwl",
        "che419.rwl",
        "finl049.rwl",
        "germ001.rwl",
        "ital019.rwl",
        "swed321.rwl",
        "swit240.rwl",
    ],
)
def test_invariants_hold(name):
    result = parse(name)
    assert result.series, "fixture produced no series"
    for s in result.series:
        assert s.last_year >= s.first_year
        assert s.n_rings == s.last_year - s.first_year + 1
        assert len(s.values) == s.n_rings
        assert 0 < s.n_measured <= s.n_rings
        assert all(v >= 0 for v in s.values if v is not None)
        assert s.precision_mm in (0.01, 0.001)


def test_series_ids_are_unique_within_a_file():
    for name in ("germ001.rwl", "swit240.rwl", "che419.rwl"):
        ids = [s.series_id for s in parse(name).series]
        assert len(ids) == len(set(ids))


def test_header_lines_are_not_mistaken_for_data():
    """ITRDB's three header lines must not become a bogus series."""
    result = parse("germ001.rwl")
    # Header lines carry 1/2/3 in the year column; none should survive.
    assert all(s.n_rings > 1 for s in result.series)
    assert all(s.first_year > 1000 for s in result.series)


def test_html_error_page_yields_no_series(tmp_path):
    """A saved 404 page must parse to nothing rather than inventing logs."""
    bogus = tmp_path / "germ002.rwl"
    bogus.write_text("<!DOCTYPE HTML>\n<html><head>\n<title>404 Not Found</title>\n")
    assert parse_rwl(str(bogus)).series == []
