"""Named places on both sides of every edge of the expanded-Europe outline."""

from __future__ import annotations

import pytest

from ehd.region import in_scope

INSIDE = {
    "Reykjavik": (64.15, -21.94),
    "Jan Mayen": (71.0, -8.3),
    "Svalbard, Longyearbyen": (78.22, 15.65),
    "Novaya Zemlya": (73.0, 55.0),
    "Ponta Delgada, Azores": (37.74, -25.67),
    "Madeira": (32.65, -16.91),
    "Tenerife": (28.29, -16.63),
    "Ifrane, Middle Atlas cedars": (33.53, -5.11),
    "Morocco's southernmost tree-ring site": (32.3, -5.5),
    "Tunisia, Ain Draham": (36.78, 8.69),
    "Jebel Akhdar, Cyrenaica": (32.5, 21.7),
    "Lebanon, Barouk cedars": (33.69, 35.69),
    "Cyprus, Troodos": (34.94, 32.86),
    "Jordan, Ajloun": (32.33, 35.75),
    "Jerusalem": (31.77, 35.21),
    "Georgia, Borjomi": (41.84, 43.38),
    "Armenia, Dilijan": (40.74, 44.86),
    "Azerbaijan, Lankaran": (38.75, 48.85),
    "Iran, Golestan forest": (37.4, 55.8),
    "Iran, Hyrcanian forest near Nowshahr": (36.6, 51.5),
    "Turkey, Hakkari": (37.57, 43.74),
    "Kola Peninsula": (68.4, 35.3),
    "North Urals timberline (russ003)": (59.6, 59.2),
    "Subpolar Urals (russ002)": (64.7, 60.0),
    "Volga, Samara": (53.2, 50.15),
    "Oral, west of the Ural River": (51.2, 51.0),
}

OUTSIDE = {
    "Greenland, Tasiilaq": (65.6, -37.6),
    "Greenland, Scoresby Sund": (70.48, -21.97),
    "Greenland, northeast": (80.0, -16.0),
    "Cape Verde": (16.0, -24.0),
    "Western Sahara, Dakhla": (23.7, -15.9),
    "Tamanrasset, Sahara": (22.79, 5.53),
    "Cairo": (30.04, 31.24),
    "Sinai, St Catherine": (28.56, 33.95),
    "Alexandria (coast, treeless)": (31.0, 29.9),
    "Tehran": (35.69, 51.39),
    "Zagros, Iran": (33.5, 48.3),
    "Mosul, Iraq": (36.34, 43.13),
    "Riyadh": (24.71, 46.68),
    "Yekaterinburg, east of the Urals": (56.84, 60.6),
    "Yamal": (70.0, 70.0),
    "Siberia (russ300)": (54.3, 89.7),
    "Aktobe, Kazakhstan": (50.28, 57.21),
    "Turkmenistan": (38.0, 58.0),
}


@pytest.mark.parametrize("name", sorted(INSIDE))
def test_inside(name):
    assert in_scope(*INSIDE[name]), name


@pytest.mark.parametrize("name", sorted(OUTSIDE))
def test_outside(name):
    assert not in_scope(*OUTSIDE[name]), name


def test_missing_coordinates_are_out():
    assert not in_scope(None, 10.0)
    assert not in_scope(50.0, None)
