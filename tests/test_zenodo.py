"""The Zenodo oak file: repeated IDs, BC years, and refusal of anything unreviewed."""

from __future__ import annotations

import pytest

from ehd import zenodo
from ehd.rwl import parse_rwl, parse_tucson_blocks


def line(series_id: str, year: int, *values: int) -> str:
    if year < 0:
        head = f"{series_id:<7.7}{year:>5}"
    else:
        head = f"{series_id:<8.8}{year:>4}"
    return head + "".join(f"{v:>6}" for v in values)


def write(tmp_path, *lines):
    p = tmp_path / "x.tuc"
    p.write_text("\n".join(lines) + "\n")
    return str(p)


def test_repeated_id_stays_two_trees(tmp_path):
    path = write(tmp_path,
                 line("ALTE", -6227, 316, 245, 240, 999),
                 line("ALTE", -4363, 100, 101, 999))
    series = parse_tucson_blocks(path).series
    assert [(s.series_id, s.first_year, s.last_year, s.values) for s in series] == [
        ("ALTE", -6227, -6225, [316, 245, 240]),
        ("ALTE", -4363, -4362, [100, 101]),
    ]
    # Why this function exists: the ID-keyed parser makes one series of them.
    assert len(parse_rwl(path).series) == 1


def test_block_runs_across_lines_and_decade_boundary(tmp_path):
    path = write(tmp_path,
                 line("PETT  5", -6101, 10),
                 line("PETT  5", -6100, 11, 12, 999))
    s = parse_tucson_blocks(path).series[0]
    assert (s.first_year, s.last_year, s.values) == (-6101, -6099, [10, 11, 12])


def test_missing_ring_is_none_not_a_width(tmp_path):
    s = parse_tucson_blocks(write(tmp_path, line("A", 1000, 5, -999, 7, 999))).series[0]
    assert s.values == [5, None, 7]
    assert s.n_measured == 2


@pytest.mark.parametrize("lines", [
    (line("A", 1000, 5, 6), line("A", 1010, 7, 999)),     # a hole in the years
    (line("A", 1000, 5, 6), line("B", 1002, 7, 999)),     # ID changes mid-series
    (line("A", 1000, 5, 6),),                             # no stop marker
    (line("A", 1000, 5, 999, 6),),                        # a ring after the stop
    (line("A", 1000, 5, -9999),),                         # 0.001 mm: 999 is a real ring
])
def test_irregular_files_warn(tmp_path, lines):
    assert parse_tucson_blocks(write(tmp_path, *lines)).warnings


def test_ids_are_unique_and_only_repeats_are_numbered():
    assert zenodo.unique_ids(["ALTE", "STEI108", "PETT  5", "ALTE"]) == [
        "ALTE (1)", "STEI108", "PETT 5", "ALTE (2)"]


def test_refuses_a_file_that_is_not_the_reviewed_one(tmp_path):
    with pytest.raises(zenodo.ZenodoMismatch):
        zenodo.build_logs(path=write(tmp_path, line("A", 1000, 5, 999)))


def test_refuses_a_missing_file(tmp_path):
    with pytest.raises(zenodo.ZenodoMismatch):
        zenodo.build_logs(path=str(tmp_path / "absent.tuc"))
