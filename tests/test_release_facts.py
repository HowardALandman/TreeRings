"""The fact extraction, on payloads small enough to count by hand."""

import array

import pytest

from scripts.release_facts import alive_counts, bc_or_ce, facts_of


def payload(spans, dating=("absolute",)):
    index = {
        "n_logs": len(spans),
        "sites": [{"dating": d} for d in dating],
        "year_min": min(s[0] for s in spans),
        "year_max": max(s[1] for s in spans),
        "unified_rows": 3,
        "stats": {"pangaea_plotted": 1, "logs_floating": 2, "logs_withdrawn": 4,
                  "sites_withdrawn": 1},
    }
    values = array.array("i")
    for first, last in spans:
        values.extend((first, last, 0, 0, 0, 0))
    return index, values.tobytes()


def test_year_zero_is_one_bc():
    assert bc_or_ce(0) == "1 BC"
    assert bc_or_ce(-4999) == "5000 BC"
    assert bc_or_ce(1) == "1 CE"


def test_alive_counts_both_end_years():
    assert alive_counts([(1, 2), (2, 3)]) == {1: 1, 2: 2, 3: 1}


def test_facts_read_counts_by_astronomical_year():
    facts = facts_of(*payload([(-6000, -5000), (-4999, 1), (1, 1971), (1971, 2000)]))
    assert facts["alive"] == {"5000 BC": 1, "1 CE": 2, "1971 CE": 2}
    assert facts["by_source"] == {"itrdb": 3, "pangaea": 1, "zenodo": 0}
    assert facts["hole"] is None


def test_hole_is_named_by_the_logs_either_side():
    # Last ring -11745 is 11746 BC; first ring -5407 is 5408 BC.
    facts = facts_of(*payload([(-11800, -11745), (-5407, 1), (1, 1971)]))
    assert facts["hole"] == {"last_alive_before": "11746 BC",
                             "first_alive_after": "5408 BC", "empty_years": 6338 - 1}


def test_a_second_hole_stops_rather_than_misstates():
    with pytest.raises(ValueError, match="more than one hole"):
        facts_of(*payload([(-100, -90), (-50, -40), (1, 1971)]))


def test_truncated_payload_is_refused():
    index, blob = payload([(1, 1971)])
    with pytest.raises(ValueError, match="ints"):
        facts_of(index, blob[:-4])
