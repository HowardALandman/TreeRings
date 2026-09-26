"""Calendar anchors for floating collections.

The failure this guards against is a subfossil log drawn at a confident
calendar date that nobody published.  Each anchor is checked at both ends of
the declared span, so these tests pin both that the real files anchor exactly
where their depositors say, and that a span which does not fit is refused
rather than approximated.
"""

from __future__ import annotations

import os

import pytest

from ehd import anchors
from ehd.anchors import Anchor, AnchorMismatch
from ehd.rwl import parse_rwl
from ehd.sweep import KNOWN_FLOATING

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name: str):
    return parse_rwl(os.path.join(FIXTURES, name)).series


def bp(first: int, last: int) -> dict:
    return {"declared_first": first, "declared_last": last}


def test_fra053_ring_one_is_first_year_bp():
    # Ordinals 1..434 against declared 14378..13945 BP: 434 years both ways.
    series = load("fra053.rwl")
    shift = anchors.offset(series, bp(14378, 13945), anchors.ANCHORS["fra053"])
    shifted = anchors.shift_series(series, shift)
    assert min(s.first_year for s in shifted) == 1950 - 14378 == -12428
    assert max(s.last_year for s in shifted) == 1950 - 13945 == -11995


def test_brit100_anchors_on_its_replicated_span():
    # The full span 630..1082 is 453 years against 418 declared; the span
    # covered by >= 2 series, 635..1052, is 418 exactly.  The earliest ring
    # (630) is a single series and sits 5 years before the anchored 4612 BP.
    series = load("brit100.rwl")
    assert anchors.reference_span(series, "replicated") == (635, 1052)
    shift = anchors.offset(series, bp(4612, 4195), anchors.ANCHORS["brit100"])
    assert 635 + shift == 1950 - 4612
    assert 1052 + shift == 1950 - 4195
    assert min(s.first_year for s in anchors.shift_series(series, shift)) == -2667


def test_brit100_full_span_reading_is_refused():
    # The literal "earliest ring = 4612 BP" reading misses the declared end by
    # 35 years, and must fail rather than be taken.
    with pytest.raises(AnchorMismatch):
        anchors.offset(load("brit100.rwl"), bp(4612, 4195), Anchor("full", 6, ""))


@pytest.mark.parametrize("declared", [(14379, 13945), (14378, 13944), (14378, 13946)])
def test_one_year_of_drift_is_refused(declared):
    # If the archive edits either end, the logs must stop being drawn at the
    # reviewed position rather than move silently.
    with pytest.raises(AnchorMismatch):
        anchors.offset(load("fra053.rwl"), bp(*declared), anchors.ANCHORS["fra053"])


def test_ce_ordered_span_is_refused():
    with pytest.raises(AnchorMismatch):
        anchors.offset(load("fra053.rwl"), bp(1, 434), anchors.ANCHORS["fra053"])


@pytest.mark.parametrize("basis", ["full", "replicated"])
def test_swiss_umbrella_span_does_not_anchor(basis):
    # swit240 declares a rounded 15000..14000 BP for 1,382 measured ordinals:
    # a site-wide bracket, not a position.  Neither reading may place it.
    with pytest.raises(AnchorMismatch):
        anchors.offset(load("swit240.rwl"), bp(15000, 14000), Anchor(basis, 0, ""))


def test_anchors_only_cover_known_floating_collections():
    # An anchor on a calendar-dated site would shift it by thousands of years.
    # corpus.build_logs also refuses this at build time.
    assert set(anchors.ANCHORS) <= KNOWN_FLOATING
    assert not any(site.startswith("swit") for site in anchors.ANCHORS)
