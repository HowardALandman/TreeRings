"""NCEI withdraws studies by note, not by deleting the file.

A withdrawn study keeps its record; the record's ``studyNotes`` gains a dated
removal line and its file list drops the ``.rwl``.  The file stays in the
directory listing and its template header still reads as live.  The pipeline
defines the corpus by that listing, so for a year 3,424 logs from 25 withdrawn
studies were plotted - the whole Maessen Dutch set among them, removed
2025-07-31 because NETH025's check sheet found "no common signal".

These tests pin the note parser on every wording seen in the corpus, and the
build's refusal to plot a known-withdrawn collection.
"""

from __future__ import annotations

import pytest

from ehd import corpus
from ehd.emit import withdrawal_problems
from ehd.harvest import withdrawal

# Real studyNotes, verbatim from the live records of 2026-10-02 (with the
# API's \r\n line endings).
REMOVED = [
    # NETH025, study 3912
    ("31-Jul-2025: Removed - Data did not meet ITRDB standards. See Comments in "
     "Text file.\r\nNOAA Template Chronology file added 2018-12-19. NOAA Template "
     "Raw Measurements file added 2019-02-05.",
     "31-Jul-2025: Removed - Data did not meet ITRDB standards. See Comments in "
     "Text file."),
    # ITAL017, study 4079 - trailing spaces
    ("9-Jun-2026: Removed - Data did not meet ITRDB standards. See statistics in "
     "Text file.   ",
     "9-Jun-2026: Removed - Data did not meet ITRDB standards. See statistics in "
     "Text file."),
    # GERM017, study 2704
    ("30-Jul-2025: Study Removed - data was mean curves of GERM016  \r\nNOAA "
     "Template Chronology file added 2018-12-19.",
     "30-Jul-2025: Study Removed - data was mean curves of GERM016"),
    # CHE602, study 41999
    ("21-Aug-2025: Study Removed - repeat data; study was a resubmission of CHE413",
     "21-Aug-2025: Study Removed - repeat data; study was a resubmission of CHE413"),
    # SWIT338, study 16912 - the file is gone, the study is not
    ("10-Dec-2025: RWL file removed due to crossdating issues. NOAA Template Raw "
     "Measurements file added 2019-02-05.",
     "10-Dec-2025: RWL file removed due to crossdating issues. NOAA Template Raw "
     "Measurements file added 2019-02-05."),
]


@pytest.mark.parametrize("notes,statement", REMOVED)
def test_every_removal_wording_is_read(notes, statement):
    assert withdrawal(notes) == statement


@pytest.mark.parametrize(
    "notes",
    [
        "",
        None,
        "NOAA Template Raw Measurements file added 2019-02-05.",
        # A real study description.  "removed" is about the timbers.
        "Ring width series from five timbers removed from the Great Tower at St "
        "Mary Magdalen Collage during renovation",
        # A dated edit that is not a removal (NOR051).
        "22-Jun-2026 Low outliers multiplied by 10- NK159. Entire file divided by 10",
    ],
)
def test_other_notes_are_not_withdrawals(notes):
    assert withdrawal(notes) == ""


def log(site: str, withdrawn: str = "") -> corpus.Log:
    return corpus.Log(key=f"{site}/A", site=site, series_id="A", first_year=1900,
                      last_year=1950, n_measured=51, values=[], variant="",
                      withdrawn=withdrawn)


def test_known_withdrawn_collection_that_reads_live_fails_the_build():
    # The failure this guards against: a harvest that stops seeing the notes.
    problems = withdrawal_problems([log("neth031"), log("neth025", "x")])
    assert len(problems) == 1 and problems[0].startswith("neth031:")


def test_known_withdrawn_collection_absent_from_corpus_is_fine():
    # NCEI may yet delete the files; that is not a failure.
    assert withdrawal_problems([log("brit036")]) == []


def test_known_withdrawn_covers_the_whole_maessen_set():
    maessen = {f"neth0{n}" for n in (20, 21, 22, 23, 24, 25, 26,
                                     28, 29, 30, 31, 32, 33, 34)}
    assert maessen <= corpus.KNOWN_WITHDRAWN
    assert len(corpus.KNOWN_WITHDRAWN) == 25
    # The Jansma oak collections, NETH001-019, are not withdrawn.
    assert not any(f"neth0{n:02d}" in corpus.KNOWN_WITHDRAWN for n in range(1, 20))
