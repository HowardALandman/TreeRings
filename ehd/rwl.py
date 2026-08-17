"""Parser for the Tucson (ITRDB) decadal ring-width format, ``.rwl``.

The format is fixed-width, not whitespace-delimited.  This matters: series IDs
routinely run straight into the year with no separator (``0003401Q1890`` in
``ital019.rwl``), so a whitespace split silently drops ~a third of the corpus.

Layout of a data line::

    col  1-8    series ID
    col  9-12   year, right-aligned
    col 13-72   ten value fields, 6 characters each
    col 73+     ignored (some files repeat the site name here)

BC years borrow column 8 for the minus sign, e.g. ``C002   -2894``, so the year
field is read as columns 8-12 when a ``-`` sits in column 8.

Values on a line begin at the stated year and run consecutively.  A series' first
line may start mid-decade (3 values at 1847 = 1847, 1848, 1849); subsequent lines
start on decade boundaries.  ``year + i`` handles both cases uniformly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# End-of-series sentinel, and the precision it implies.  Only one of these is
# active per file, and which one must be decided *before* parsing:
#
#   -9999  terminator in files measured to 0.001 mm
#     999  terminator in files measured to 0.01 mm
#
# The distinction is not cosmetic.  In a 0.001 mm file, 999 is a perfectly
# ordinary 0.999 mm ring, so treating it as a terminator there truncates real
# logs.  _detect_stop_marker() resolves this per file.
STOP_0001 = -9999
STOP_001 = 999

# -999 marks an *absent* measurement, not the end of a series.  It occurs in
# long runs mid-series (che419.rwl leaves 1870-1889 unmeasured and then resumes
# with real data), so treating it as a terminator silently shortens logs by
# decades.  Missing values are held as None and trimmed from the ends.
MISSING_VALUE = -999

VALUE_START = 12  # 0-indexed column where the value fields begin
VALUE_WIDTH = 6
VALUES_PER_LINE = 10
VALUE_END = VALUE_START + VALUE_WIDTH * VALUES_PER_LINE  # ignore trailing junk

# A single tree ring wider than this (in raw file units) is implausible and
# indicates a misparse rather than a real measurement.
MAX_PLAUSIBLE_VALUE = 30000
# Longest-lived plausible series.  The oldest known individual trees are ~5000
# years; anything beyond this is a parse artefact, not a tree.
MAX_PLAUSIBLE_RINGS = 6000


@dataclass
class Series:
    """One physical log: a single measured radius from a single tree.

    ``values`` is aligned to ``first_year``..``last_year`` inclusive, with None
    for years the file leaves unmeasured.  Both ends are trimmed to real
    measurements, so the year span always describes actual data.
    """

    series_id: str
    source_file: str
    first_year: int
    last_year: int
    values: list[int | None]
    precision_mm: float  # 0.01 or 0.001, decided per file

    @property
    def n_rings(self) -> int:
        """Total years spanned, measured or not - the width of the rectangle."""
        return self.last_year - self.first_year + 1

    @property
    def n_measured(self) -> int:
        return sum(v is not None for v in self.values)

    @property
    def complete(self) -> bool:
        """True when every year in the span carries a measurement."""
        return self.n_measured == self.n_rings


@dataclass
class ParseResult:
    series: list[Series] = field(default_factory=list)
    # Non-fatal oddities, one line each.  Never discarded silently.
    warnings: list[str] = field(default_factory=list)
    n_data_lines: int = 0
    n_unparsed_lines: int = 0


def _read_lines(path: str) -> list[str]:
    """Read with encoding fallback.  ITRDB files mix UTF-8, cp1252 and latin-1."""
    raw = open(path, "rb").read()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc).splitlines()
        except UnicodeDecodeError:
            continue
    # latin-1 cannot fail, but keep the fallback explicit rather than implicit.
    return raw.decode("latin-1", errors="replace").splitlines()


def _split_id_year(line: str) -> tuple[str, int] | None:
    """Split a candidate data line into (series_id, year).

    Returns None when the line is not a data line (headers, blanks, comments).
    """
    if len(line) < VALUE_START:
        return None
    # BC years borrow column 8 (0-indexed 7) for their sign.
    if line[7] == "-":
        id_part, year_part = line[:7], line[7:VALUE_START]
    else:
        id_part, year_part = line[:8], line[8:VALUE_START]
    try:
        year = int(year_part)
    except ValueError:
        return None
    series_id = id_part.strip()
    if not series_id:
        return None
    return series_id, year


def _parse_values(line: str) -> list[int] | None:
    """Read the fixed-width value fields, ignoring anything past column 72."""
    out: list[int] = []
    body = line[VALUE_START:VALUE_END]
    for i in range(0, len(body), VALUE_WIDTH):
        chunk = body[i : i + VALUE_WIDTH].strip()
        if not chunk:
            break  # trailing blanks end the line's data
        try:
            out.append(int(chunk))
        except ValueError:
            # A non-numeric field means this was never a data line.
            return None
    return out


def _iter_data_lines(lines: list[str]):
    """Yield (lineno, series_id, year, values) for every line that is real data."""
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        parsed = _split_id_year(line)
        if parsed is None:
            continue  # header or comment line
        values = _parse_values(line)
        if values is None:
            continue  # header line that happened to hold a numeric year field
        yield lineno, parsed[0], parsed[1], values


def _is_edge_filler(value: int) -> bool:
    """True for values that must not define where a series begins or ends.

    Both terminators are trimmed regardless of which one the file nominally
    uses: a single stray -9999 elsewhere in the file must not turn a real 999
    terminator into a 9.99 mm ring (finl084 does exactly that).  Negative
    values - locally absent rings recorded as flags - are trimmed at the edges
    too, since a log's span should be bounded by rings that were measured.
    Interior occurrences are left alone and handled as real data.
    """
    return value < 0 or value in (STOP_001, STOP_0001)


def _detect_stop_marker(lines: list[str]) -> tuple[int, float]:
    """Decide this file's terminator and precision before parsing it.

    A file containing -9999 anywhere is measured to 0.001 mm, and in such a file
    999 is a real 0.999 mm ring rather than a terminator.  Getting this backwards
    truncates long logs at their first sub-millimetre ring.
    """
    for _, _, _, values in _iter_data_lines(lines):
        if STOP_0001 in values:
            return STOP_0001, 0.001
    return STOP_001, 0.01


def parse_rwl(path: str) -> ParseResult:
    """Parse one ``.rwl`` file into per-log series.

    Diagnostics are returned rather than raised: a malformed line must be
    counted and reported, never dropped on the floor.
    """
    result = ParseResult()
    name = os.path.basename(path)
    lines = _read_lines(path)

    stop_marker, precision = _detect_stop_marker(lines)

    # year -> raw value, per series.  Terminators are *not* acted on while
    # reading: a 999 in a 0.01 mm file is ambiguous between "end of series" and
    # a real 9.99 mm ring, and only its position settles which it is.  We keep
    # everything and resolve the ambiguity by trimming from the end afterwards.
    acc: dict[str, dict[int, int]] = {}

    for lineno, series_id, year, values in _iter_data_lines(lines):
        if not values:
            result.n_unparsed_lines += 1
            result.warnings.append(f"{name}:{lineno}: data line with no values")
            continue

        result.n_data_lines += 1
        series = acc.setdefault(series_id, {})

        for i, value in enumerate(values):
            y = year + i
            if y in series and series[y] != value:
                result.warnings.append(
                    f"{name}:{lineno}: series {series_id!r} repeats year {y} "
                    f"with a different value"
                )
            series[y] = value

    for series_id, by_year in acc.items():
        years = sorted(by_year)
        # Trim sentinels and unmeasured rings off both ends, so the surviving
        # span is bounded by real measurements.  Whatever terminator survives
        # in the interior was a genuine measurement all along.
        lo, hi = 0, len(years) - 1
        while lo <= hi and _is_edge_filler(by_year[years[lo]]):
            lo += 1
        while hi >= lo and _is_edge_filler(by_year[years[hi]]):
            hi -= 1
        if lo > hi:
            result.warnings.append(
                f"{name}: series {series_id!r} has no measured rings - skipped"
            )
            continue

        first, last = years[lo], years[hi]
        span = last - first + 1
        if span > MAX_PLAUSIBLE_RINGS:
            result.warnings.append(
                f"{name}: series {series_id!r} spans {span} years - "
                f"rejected as implausible"
            )
            continue

        vals: list[int | None] = []
        n_absent = 0
        n_interior_terminator = 0
        for y in range(first, last + 1):
            v = by_year.get(y)
            if v is None or v == MISSING_VALUE:
                vals.append(None)  # unmeasured year inside the span
                continue
            if v == stop_marker:
                n_interior_terminator += 1
            if v < 0:
                # dplR renders these as zero: a locally absent ring, recorded
                # by some labs as a negative flag rather than a 0.
                n_absent += 1
                vals.append(0)
                continue
            vals.append(v)

        if n_interior_terminator:
            result.warnings.append(
                f"{name}: series {series_id!r} keeps {n_interior_terminator} "
                f"interior {stop_marker} value(s) as real measurements"
            )
        if n_absent:
            result.warnings.append(
                f"{name}: series {series_id!r} has {n_absent} locally absent "
                f"ring(s) recorded as negative values"
            )
        if any(v is not None and v > MAX_PLAUSIBLE_VALUE for v in vals):
            result.warnings.append(
                f"{name}: series {series_id!r} contains implausibly large values"
            )

        result.series.append(
            Series(
                series_id=series_id,
                source_file=name,
                first_year=first,
                last_year=last,
                values=vals,
                precision_mm=precision,
            )
        )

    result.series.sort(key=lambda s: (s.first_year, s.series_id))
    return result
