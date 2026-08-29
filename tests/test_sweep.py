"""Tests for the span sweep - the report that goes to NCEI.

The sweep's output is a list of corrections we ask a data manager to make to a
public archive, so the expensive failure is not a crash but a plausible-looking
wrong row.  Two ways to produce one, both of which happened while writing it:

* asking for a *floating* collection to be "corrected", which would delete the
  only absolute anchor its logs have;
* reporting a record that is describing a different file of the same study -
  the earlywood or maximum-density variant measured on the same trees.

Both are pinned here on the real collections that exposed them.
"""

from __future__ import annotations

from ehd.sweep import Row, classify_span, explain_by_sibling, header_span, partition


def row(**kw) -> Row:
    kw.setdefault("filename", "x.rwl")
    kw.setdefault("site", "x")
    return Row(**kw)


# --- how a declared span relates to its data --------------------------------


def test_classify_span_covers_every_relation():
    assert classify_span((1747, 1988), (1747, 1988)) == "exact"
    assert classify_span((1276, 1974), (1789, 1974)) == "declared narrower"
    assert classify_span((1107, 1827), (1107, 1978)) == "declared wider"
    assert classify_span((1659, 1975), (1815, 1982)) == "declared offset"
    assert classify_span((1834, 2006), (-66, 106)) == "disjoint"


def test_touching_spans_are_not_disjoint():
    # A one-year overlap is still an overlap; only a true gap is disjoint.
    assert classify_span((1800, 1900), (1900, 2000)) == "declared offset"
    assert classify_span((1800, 1899), (1900, 2000)) == "disjoint"


# --- the record that describes a sibling file -------------------------------

NORW = {
    "norw011.rwl": (1409, 1997),
    "norw011e.rwl": (1550, 1997),
    "norw011l.rwl": (1550, 1997),
}
ESP = {"esp099.rwl": (1272, 2015), "esp099x.rwl": (1209, 2014)}


def test_a_span_matching_an_earlywood_sibling_is_not_a_defect():
    r = row(filename="norw011.rwl", site="norw011",
            measured=(1409, 1997), declared=(1550, 1997), cls="declared narrower")
    assert explain_by_sibling(r, NORW, {"norw011": list(NORW)}) == "norw011e.rwl"


def test_a_span_matching_the_union_of_variants_is_not_a_defect():
    # ESP099 declares 1209-2015: no single file, but exactly the two together.
    r = row(filename="esp099.rwl", site="esp099",
            measured=(1272, 2015), declared=(1209, 2015), cls="declared wider")
    assert explain_by_sibling(r, ESP, {"esp099": list(ESP)}).startswith("union of ")


def test_a_genuine_mismatch_is_not_explained_away():
    # AUST003 has no variants at all, so nothing can excuse 1789 against 1276.
    r = row(filename="aust003.rwl", site="aust003",
            measured=(1276, 1974), declared=(1789, 1974), cls="declared narrower")
    assert explain_by_sibling(r, {"aust003.rwl": (1276, 1974)},
                              {"aust003": ["aust003.rwl"]}) == ""


def test_a_sole_file_cannot_explain_itself():
    r = row(filename="a.rwl", site="a", measured=(1, 9), declared=(1, 9))
    assert explain_by_sibling(r, {"a.rwl": (1, 9)}, {"a": ["a.rwl"]}) == ""


# --- what reaches the report ------------------------------------------------


def test_floating_collections_never_reach_the_reportable_set():
    rows = [
        row(filename="swit195.rwl", site="swit195", cls="disjoint", floating=True),
        row(filename="fra053.rwl", site="fra053", cls="disjoint", floating=True),
        row(filename="aust003.rwl", site="aust003", cls="declared narrower"),
    ]
    part = partition(rows)
    assert [r.site for r in part["reportable"]] == ["aust003"]
    assert {r.site for r in part["do_not_touch"]} == {"swit195", "fra053"}


def test_partition_accounts_for_every_row():
    """Nothing may fall between the groups; a dropped row is a silent omission."""
    rows = [
        row(site="a", cls="exact"),
        row(site="b", cls="declared wider"),
        row(site="c", cls="disjoint", floating=True),
        row(site="d", cls="declared narrower", explained_by="d_e.rwl"),
        row(site="e", cls="no record span", study_id="2710"),
        row(site="f", cls="no record span"),
    ]
    part = partition(rows)
    assert sum(len(v) for v in part.values()) == len(rows)
    assert len(part["describes_sibling"]) == 1
    assert len(part["no_declared_span"]) == 1
    assert len(part["unresolved"]) == 1


# --- the advisory legacy-header read ----------------------------------------


def test_header_span_reads_the_tucson_second_line(tmp_path):
    p = tmp_path / "brit.rwl"
    p.write_text(
        "346    1 ROSTREVOR\n"
        "346    2 N. IRELAND   QUPE            197  5506N00612W270 21 1  812 1458\n"
    )
    assert header_span(str(p)) == (812, 1458)


def test_an_unparseable_header_is_unknown_not_a_mismatch(tmp_path):
    """The legacy header's layout varies; a bad read must not invent a defect."""
    p = tmp_path / "x.rwl"
    p.write_text("101    1 JURA\n101    2 FRANCE       JURA MOUNTAINS     ABAL\n")
    assert header_span(str(p)) is None


def test_implausible_years_are_rejected(tmp_path):
    p = tmp_path / "x.rwl"
    p.write_text("a\nb site 950 52.13 4.483\n")  # trailing numbers are coordinates
    assert header_span(str(p)) is None
