"""The directory listing is how we learn the archive changed under us.

`fetch --refresh` exists because a cached corpus looks identical to a current
one.  The case that proves it: on 2026-08-19 NCEI rewrote brit.rwl's header
line from "1750 1975" to " 812 1458" - a correction we had asked for - and the
file's length did not change, because the replacement is the same width.  A
size comparison sees nothing.  Only the listing's timestamp catches it.

The listing parser is also a silent-failure risk in its own right: if the
markup changes, a regex that matches nothing reports an empty archive as a
successful run.  So it is checked against a second, cruder scan of the same
HTML before it is trusted.
"""

from __future__ import annotations

import os
import time

import pytest

from ehd.fetch import _HREF_RE, _ROW_RE, list_europe_index, stale_files

LISTING = """\
<html><body><table>
<tr><td><a href="brit.rwl">brit.rwl</a></td>
<td align="right">2026-08-19 19:11</td><td align="right">21438</td><td> </td></tr>
<tr><td><a href="fran10.rwl">fran10.rwl</a></td>
<td align="right">2023-01-12 17:36</td><td align="right">1085948</td><td> </td></tr>
<tr><td><a href="fran10-rwl-noaa.txt">fran10-rwl-noaa.txt</a></td>
<td align="right">2026-08-19 18:58</td><td align="right">1348777</td><td> </td></tr>
</table></body></html>
"""


def test_row_parser_and_href_scan_agree_on_this_listing():
    rows = {name for name, _, _ in _ROW_RE.findall(LISTING)}
    assert rows == set(_HREF_RE.findall(LISTING))


def test_a_markup_change_raises_rather_than_reporting_an_empty_archive(monkeypatch):
    # The failure this guards against: the row regex stops matching, the href
    # scan still finds files, and a run that downloaded nothing looks clean.
    broken = LISTING.replace('<td align="right">', "<td class=size>")
    monkeypatch.setattr("ehd.fetch._get", lambda url, timeout=120: broken.encode())
    with pytest.raises(RuntimeError, match="listing markup"):
        list_europe_index()


def test_listing_parses_name_date_and_size(monkeypatch):
    monkeypatch.setattr("ehd.fetch._get", lambda url, timeout=120: LISTING.encode())
    index = list_europe_index()
    assert index["brit.rwl"] == ("2026-08-19 19:11", 21438)


def write(tmp_path, name, size, mtime):
    path = tmp_path / name
    path.write_bytes(b"x" * size)
    os.utime(path, (mtime, mtime))
    return path


def epoch(stamp):
    return time.mktime(time.strptime(stamp, "%Y-%m-%d %H:%M"))


def test_same_size_but_newer_on_the_server_is_stale(tmp_path):
    """brit.rwl, exactly.  This is the case a size check cannot see."""
    write(tmp_path, "brit.rwl", 21438, epoch("2026-08-17 13:40"))
    index = {"brit.rwl": ("2026-08-19 19:11", 21438)}
    assert stale_files(["brit.rwl"], str(tmp_path), index) == ["brit.rwl"]


def test_unchanged_file_is_not_stale(tmp_path):
    write(tmp_path, "fran10.rwl", 1085948, epoch("2026-08-17 13:40"))
    index = {"fran10.rwl": ("2023-01-12 17:36", 1085948)}
    assert stale_files(["fran10.rwl"], str(tmp_path), index) == []


def test_size_mismatch_is_stale_even_when_the_date_is_old(tmp_path):
    write(tmp_path, "fran10.rwl", 999, epoch("2026-08-17 13:40"))
    index = {"fran10.rwl": ("2023-01-12 17:36", 1085948)}
    assert stale_files(["fran10.rwl"], str(tmp_path), index) == ["fran10.rwl"]


def test_absent_file_is_stale(tmp_path):
    index = {"neth005.rwl": ("2020-01-09 13:14", 10)}
    assert stale_files(["neth005.rwl"], str(tmp_path), index) == ["neth005.rwl"]


def test_a_days_slack_absorbs_the_listings_unstated_timezone(tmp_path):
    """The listing prints server-local time with no zone marker.

    A copy is written strictly after the server mtime it was fetched from, so
    a few hours of apparent lead is timezone skew, not an edit.  A day of slack
    covers every real offset without hiding an edit, which lands days later.
    """
    write(tmp_path, "brit.rwl", 21438, epoch("2026-08-17 09:00"))
    index = {"brit.rwl": ("2026-08-17 13:11", 21438)}  # 4h "later" - EDT vs UTC
    assert stale_files(["brit.rwl"], str(tmp_path), index) == []
