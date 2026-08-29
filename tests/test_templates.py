"""The archive keeps two NOAA template families and only one is maintained.

NCEI renamed the per-study template from ``<site>-noaa.rwl`` to
``<site>-rwl-noaa.txt`` in February 2023 and changed the field vocabulary at the
same time: ``Earliest_Year``/``Most_Recent_Year`` became ``First_Year``/
``Last_Year``, ``Elevation`` became ``Elevation_m``, ``Online_Resource`` became
``NOAA_Landing_Page``.  Nothing announces this in the file.

Reading the old family got a snapshot frozen in January 2023 - the August 2026
corrections went only to the new one.  Reading the new family with the old field
names is worse than either: every field comes back empty, and an empty declared
span reads downstream as "nothing to check against" rather than as a failure.
These tests pin both halves.
"""

from __future__ import annotations

import os

from ehd.corpus import declared_span_ce, declares_years_bp, read_template_header

V2 = """\
# Study_Name: Old template
# Earliest_Year: 1600
# Most_Recent_Year: 1900
# Elevation: 500
# Online_Resource: https://example.invalid/study/1
# Site_Name: Somewhere
# Investigators: Nobody
"""

V3 = """\
#   Study_Name: New template
#   First_Year: 1747
#   Last_Year: 1988
#   Time_Unit: CE
#   Elevation_m: 950
#   Site_Name: Jura
# NOAA_Landing_Page: https://example.invalid/study/2
"""

V3_BP = """\
#   Study_Name: Late Glacial
#   First_Year: 14378
#   Last_Year: 13945
#   Elevation_m: 860
"""


def write(tmp_path, site, **families):
    (tmp_path / f"{site}.rwl").write_text("data\n")
    for suffix, body in families.items():
        name = {"v2": f"{site}-noaa.rwl", "v3": f"{site}-rwl-noaa.txt"}[suffix]
        (tmp_path / name).write_text(body)
    return os.path.join(str(tmp_path), f"{site}.rwl")


def test_v3_field_vocabulary_is_read(tmp_path):
    meta = read_template_header(write(tmp_path, "fran10", v3=V3))
    assert declared_span_ce(meta) == (1747, 1988)
    assert meta["elevation"] == "950"
    assert meta["url"] == "https://example.invalid/study/2"


def test_v2_field_vocabulary_still_works(tmp_path):
    meta = read_template_header(write(tmp_path, "old01", v2=V2))
    assert declared_span_ce(meta) == (1600, 1900)
    assert meta["elevation"] == "500"


def test_the_maintained_family_wins_the_declared_span(tmp_path):
    # The case that motivated this: fran10's v2 file still says 1943..1975
    # three years after NCEI corrected the study to 1747..1988 in the v3 file.
    path = write(tmp_path, "fran10", v2=V2, v3=V3)
    assert declared_span_ce(read_template_header(path)) == (1747, 1988)


def test_the_span_is_never_mixed_between_families(tmp_path):
    """A first year from 2023 with a last year from 2026 describes nothing.

    Descriptive fields merge freely, but the span is taken whole from whichever
    family supplies both halves.
    """
    v3_no_span = "#   Study_Name: New template\n#   Elevation_m: 950\n"
    path = write(tmp_path, "fran10", v2=V2, v3=v3_no_span)
    meta = read_template_header(path)
    assert declared_span_ce(meta) == (1600, 1900)  # v2's pair, intact
    assert meta["elevation"] == "950"  # but v3's descriptive field
    assert meta["study_name"] == "New template"


def test_missing_template_is_silent_and_empty(tmp_path):
    assert read_template_header(write(tmp_path, "germ001")) == {}


def test_bp_declaration_survives_the_new_vocabulary(tmp_path):
    # fra053: no Time_Unit at all, and the years count backwards.  The ordering
    # is the only mark, and it has to survive the field rename.
    meta = read_template_header(write(tmp_path, "fra053", v3=V3_BP))
    assert declares_years_bp(meta)
    assert declared_span_ce(meta) == (-12428, -11995)
