"""Which sites the web build shows: expanded Europe (the Western Palearctic).

Howard's scope (2026-10-24): Europe to the Urals, Turkey, Cyprus, the Caucasus
(Georgia, Armenia, Azerbaijan), the Levant, Iran's Caspian (Hyrcanian)
forests, North Africa north of the Sahara, and Macaronesia (Azores, Madeira,
Canaries).  The Sahara is the southern edge, as in the biogeographic Western
Palearctic.  The test is on site coordinates, never on which ITRDB folder a
file sits in: NCEI files European Russia under asia/ and the Maghreb under
africa/.

The polygon is drawn by hand and its edges are judgement, not survey lines:

* East: the Ural crest (about 60°E, bending to 66°E in the Polar Urals), then
  the Ural River from Orsk west to Oral and south to the Caspian at Atyrau.
* Southeast: around the Caspian to Iran's Caspian forests, then back west
  along the Alborz and the Turkish-Iraqi border at ~37°N.  Iraq and the Iranian
  Zagros are outside: not in the agreed list, although their oak forests are
  continuous with southeast Turkey's.
* South: the Levant to Aqaba and Gaza, then the Sahara's northern edge -
  the Egyptian and Libyan coast, the Tunisian and Saharan Atlas, south of the
  High and Anti-Atlas to Tarfaya and the Canaries.
* Northwest: Iceland and Jan Mayen in, Greenland out.

``tests/test_region.py`` pins named places on both sides of every edge, so a
change to the outline shows up as a failing place, not as a silently different
corpus.
"""

from __future__ import annotations

# (lon, lat), clockwise from the northwest.
WESTERN_PALEARCTIC: list[tuple[float, float]] = [
    (-10.0, 82.0),   # north of Svalbard and Franz Josef Land
    (70.0, 82.0),
    (66.5, 69.0),    # Polar Urals, north end
    (66.0, 67.0),
    (60.0, 61.0),    # Northern Urals crest
    (59.5, 55.0),    # Middle Urals
    (59.0, 53.0),    # Southern Urals, Ural River headwaters
    (58.5, 51.2),    # Orsk
    (51.4, 51.2),    # Oral (Uralsk)
    (51.9, 47.0),    # Atyrau, where the Ural River meets the Caspian
    (52.0, 41.0),    # across the Caspian
    (56.2, 37.8),    # Golestan, east end of the Hyrcanian forests
    (56.2, 36.3),
    (48.5, 36.3),    # Alborz ridge, west
    (48.5, 37.0),
    (44.5, 37.0),    # Turkey-Iran-Iraq
    (42.35, 37.1),   # Turkey-Syria-Iraq tripoint
    (41.0, 34.4),    # Syria-Iraq border
    (38.8, 33.4),
    (39.0, 32.0),    # Jordan
    (36.0, 29.2),    # Aqaba
    (34.9, 29.5),    # Eilat
    (34.2, 31.2),    # Gaza; Sinai and the Nile Delta stay out
    (25.0, 31.2),    # Egyptian coast
    (19.0, 30.0),    # Gulf of Sirte
    (12.0, 31.5),    # Jebel Nafusa
    (9.0, 32.5),     # southern Tunisia
    (3.0, 33.0),     # Saharan Atlas
    (-1.0, 32.0),    # Figuig
    (-6.0, 30.0),    # south of the High Atlas
    (-9.8, 29.5),    # Anti-Atlas
    (-12.0, 28.0),   # Tarfaya
    (-18.5, 27.5),   # south of the Canaries
    (-32.0, 27.5),
    (-32.0, 63.0),   # Azores and Iceland's longitude band ...
    (-26.0, 63.0),
    (-26.0, 67.5),   # ... west of Iceland, east of Greenland
    (-14.0, 69.5),   # between Scoresby Sund and Jan Mayen
    (-14.0, 81.0),   # NE Greenland reaches ~11°W only above 81°N
]


def _inside(lon: float, lat: float, poly: list[tuple[float, float]]) -> bool:
    """Even-odd ray casting.  Good enough at this scale: no edge passes near a
    site within the precision of its published coordinates (2 decimals)."""
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > lat) != (yj > lat):
            x = xi + (lat - yi) * (xj - xi) / (yj - yi)
            if lon < x:
                inside = not inside
        j = i
    return inside


def in_scope(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    return _inside(float(lon), float(lat), WESTERN_PALEARCTIC)
