"""The map's base layer: clipping, quantization, and that every site is on it.

The geometry here is only orientation for the circles, but it is the kind of
thing that goes wrong invisibly - a clip that drops a ring, or a box that cuts
off a corner of the corpus, still draws a plausible-looking map.
"""

from __future__ import annotations

import json
import os
import re

import pytest

from ehd import basemap

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
BOX = (0.0, 0.0, 10.0, 10.0)


def area(ring):
    n = len(ring)
    return abs(sum(ring[k][0] * ring[(k + 1) % n][1] - ring[(k + 1) % n][0] * ring[k][1]
                   for k in range(n))) / 2


def test_ring_inside_is_unchanged_apart_from_the_closing_vertex():
    ring = [(1, 1), (4, 1), (4, 4), (1, 1)]
    assert basemap.clip_ring(ring, BOX) == [(1, 1), (4, 1), (4, 4)]


def test_ring_outside_vanishes():
    assert basemap.clip_ring([(20, 20), (30, 20), (30, 30)], BOX) == []


def test_straddling_square_keeps_exactly_the_inside_area():
    # 6..14 x -2..4 overlaps the box in 6..10 x 0..4 = 16.
    ring = [(6, -2), (14, -2), (14, 4), (6, 4)]
    assert area(basemap.clip_ring(ring, BOX)) == pytest.approx(16.0)


def test_box_inside_a_ring_becomes_the_box():
    # The Eurasia polygon is far larger than the box: clipping must keep it.
    ring = [(-50, -50), (50, -50), (50, 50), (-50, 50)]
    assert area(basemap.clip_ring(ring, BOX)) == pytest.approx(100.0)


def test_concave_ring_area_survives_clipping():
    # A U shape whose two arms leave through the top edge and come back.
    u = [(1, 1), (9, 1), (9, 15), (7, 15), (7, 3), (3, 3), (3, 15), (1, 15)]
    # Inside the box: base 8x2 = 16, plus two arms 2 wide x 7 tall = 28.
    assert area(basemap.clip_ring(u, BOX)) == pytest.approx(44.0)


def test_line_is_split_where_it_leaves_the_box():
    line = [(1, 1), (2, 2), (20, 2), (3, 3), (4, 4), (5, 5)]
    assert basemap.clip_line(line, BOX) == [[(1, 1), (2, 2)], [(3, 3), (4, 4), (5, 5)]]


def test_quantize_drops_repeats_and_the_closing_vertex():
    pts = [(1.0, 2.0), (1.001, 2.001), (1.5, 2.0), (1.0, 2.0)]
    assert basemap.quantize(pts, closed=True) == [100, 200, 150, 200]
    assert basemap.quantize(pts, closed=False) == [100, 200, 150, 200, 100, 200]


def test_sources_are_pinned_to_a_tag_and_a_digest():
    assert re.fullmatch(r"v\d+\.\d+\.\d+", basemap.NE_TAG)
    assert basemap.NE_TAG in basemap.NE_BASE
    for fname, digest in basemap.SOURCES.values():
        assert fname.endswith(".geojson")
        assert re.fullmatch(r"[0-9a-f]{64}", digest)


def built_index():
    path = os.path.join(WEB, "data", "index.json")
    if not os.path.exists(path):
        pytest.skip("web/data not built; run python -m ehd.emit")
    blob = open(path, "rb").read()
    if not blob.lstrip().startswith(b"{"):
        blob = pytest.importorskip("brotli").decompress(blob)
    return json.loads(blob)


def test_every_mapped_site_lies_inside_the_basemap():
    outside = basemap.sites_outside(built_index()["sites"])
    assert not outside, f"widen basemap.BBOX: {outside}"


def test_built_basemap_matches_the_module():
    path = os.path.join(WEB, "data", "basemap.json")
    if not os.path.exists(path):
        pytest.skip("basemap not built; run python -m ehd.basemap")
    bm = json.load(open(path))
    assert bm["scale"] == basemap.SCALE
    assert bm["bbox"] == list(basemap.BBOX)
    assert basemap.NE_TAG in bm["source"]
    x0, y0, x1, y1 = (round(v * basemap.SCALE) for v in basemap.BBOX)
    for layer in ("land", "lakes", "borders"):
        assert bm[layer], f"{layer} is empty"
        for part in bm[layer]:
            assert len(part) % 2 == 0
            assert all(x0 <= x <= x1 for x in part[0::2])
            assert all(y0 <= y <= y1 for y in part[1::2])
