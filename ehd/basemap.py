"""Build the map viewer's base layer from Natural Earth.

The viewer draws its own outlines instead of loading map tiles, so the site
stays free of third-party requests.  This module downloads three Natural Earth
1:50m layers (land, lakes, land borders between countries), clips them to a box
around the corpus, rounds coordinates to 0.01 degrees, and writes
web/data/basemap.json.

The downloads are pinned to a release tag *and* a SHA-256 each.  The tag alone
does not stop a force-pushed tag or a corrupted cache from quietly changing the
map, and a wrong coastline is not something anyone would think to check.

1:50m is enough at the zoom levels where the coastline matters: almost every
site is inland, and 0.01 degrees (about 1 km) is finer than the data, whose
nominal resolution is tens of kilometres.

Usage:
    python -m ehd.basemap
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

from . import config, fetch

NE_TAG = "v5.1.2"
NE_BASE = f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/{NE_TAG}/geojson"

# layer -> (file, sha256), checked on every run, cached copy included.
SOURCES = {
    "land": (
        "ne_50m_land.geojson",
        "e874b27a51d146452be360cafb3cc50c86001074a67d534113e6534682f9826b",
    ),
    "lakes": (
        "ne_50m_lakes.geojson",
        "d350b75978b26fe839b797c2c529b2fb8f47fb3983c03f4964e36d5df9378a52",
    ),
    "borders": (
        "ne_50m_admin_0_boundary_lines_land.geojson",
        "2faac4f6b34386f3d21b6e018cf151f241f00e5c936d44dd17d7d9bfb147fa48",
    ),
}

# lon_min, lat_min, lon_max, lat_max.  Far wider than the corpus (9.6 W to
# 45.2 E, 34.9 N to 69.9 N in the 2026-10-18 build) because the cut is visible:
# a lon/lat edge projects to a long straight-ish coastline that is not there.
# A first try at 32 W - 62 E, 25 - 76 N showed it inside the fitted view.  The
# nearest edge of this box is 4,131 km from the projection centre, and the
# viewer's MAP_MIN_SCALE stops zooming out before a 1600 px canvas reaches it.
# A site outside the box is a build error, not a clipping decision: see
# sites_outside().
BBOX = (-75.0, 5.0, 115.0, 90.0)

SCALE = 100  # stored coordinates are integer hundredths of a degree


class ChecksumMismatch(RuntimeError):
    pass


def source_path(fname: str) -> str:
    return config.path(config.RAW, "naturalearth", NE_TAG, fname)


def load_source(fname: str, sha256: str) -> dict:
    """Return the parsed layer, downloading it first if it is not cached."""
    p = source_path(fname)
    if not os.path.exists(p):
        blob = fetch._get(f"{NE_BASE}/{fname}")
        digest = hashlib.sha256(blob).hexdigest()
        if digest != sha256:
            raise ChecksumMismatch(f"{fname}: downloaded sha256 {digest}, pinned {sha256}")
        with open(p, "wb") as fh:
            fh.write(blob)
    blob = open(p, "rb").read()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != sha256:
        raise ChecksumMismatch(
            f"{p}: sha256 {digest}, pinned {sha256}; delete it to re-download"
        )
    return json.loads(blob)


# ----------------------------------------------------------------- geometry


def clip_ring(ring: list[tuple[float, float]], bbox=BBOX) -> list[tuple[float, float]]:
    """Sutherland-Hodgman: clip a closed ring to an axis-aligned box.

    The result can carry zero-width spurs along the box edge where a concave
    ring leaves and re-enters.  They enclose no area, so they change nothing
    under a fill, which is the only way rings are drawn.
    """
    x0, y0, x1, y1 = bbox
    edges = (
        (lambda p: p[0] >= x0, lambda a, b: _at_x(a, b, x0)),
        (lambda p: p[0] <= x1, lambda a, b: _at_x(a, b, x1)),
        (lambda p: p[1] >= y0, lambda a, b: _at_y(a, b, y0)),
        (lambda p: p[1] <= y1, lambda a, b: _at_y(a, b, y1)),
    )
    out = list(ring)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    for inside, cross in edges:
        if not out:
            break
        src, out = out, []
        prev = src[-1]
        for cur in src:
            if inside(cur):
                if not inside(prev):
                    out.append(cross(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cross(prev, cur))
            prev = cur
    return out


def clip_line(line: list[tuple[float, float]], bbox=BBOX) -> list[list[tuple[float, float]]]:
    """Split a polyline into the runs that lie inside the box.

    Borders are short and the box is generous, so a segment that leaves the
    box is simply cut at the vertex that left it; the gap is off-screen at any
    zoom the viewer allows.
    """
    x0, y0, x1, y1 = bbox
    runs: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    for p in line:
        if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            cur.append(p)
        else:
            if len(cur) > 1:
                runs.append(cur)
            cur = []
    if len(cur) > 1:
        runs.append(cur)
    return runs


def _at_x(a, b, x):
    t = (x - a[0]) / (b[0] - a[0])
    return (x, a[1] + t * (b[1] - a[1]))


def _at_y(a, b, y):
    t = (y - a[1]) / (b[1] - a[1])
    return (a[0] + t * (b[0] - a[0]), y)


def quantize(points, closed: bool) -> list[int]:
    """Round to SCALE, drop repeated vertices, flatten to [x, y, x, y, ...]."""
    flat: list[int] = []
    last = None
    for x, y in points:
        q = (round(x * SCALE), round(y * SCALE))
        if q != last:
            flat.extend(q)
            last = q
    if closed and len(flat) >= 4 and flat[:2] == flat[-2:]:
        del flat[-2:]
    return flat


def ring_area2(flat: list[int]) -> int:
    """Twice the signed area of a flattened ring (shoelace)."""
    n = len(flat) // 2
    s = 0
    for k in range(n):
        x0, y0 = flat[2 * k], flat[2 * k + 1]
        x1, y1 = flat[(2 * k + 2) % (2 * n)], flat[(2 * k + 3) % (2 * n)]
        s += x0 * y1 - x1 * y0
    return s


def polygon_rings(geom: dict):
    if geom["type"] == "Polygon":
        yield from geom["coordinates"]
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            yield from poly
    else:
        raise ValueError(f"expected a polygon, got {geom['type']}")


def line_parts(geom: dict):
    if geom["type"] == "LineString":
        yield geom["coordinates"]
    elif geom["type"] == "MultiLineString":
        yield from geom["coordinates"]
    else:
        raise ValueError(f"expected a line, got {geom['type']}")


def build_rings(fc: dict) -> list[list[int]]:
    """Every ring of every polygon, clipped and quantized.

    Holes are kept as rings of their own; the viewer fills with the even-odd
    rule, which makes a hole a hole regardless of winding.
    """
    out = []
    for feat in fc["features"]:
        for ring in polygon_rings(feat["geometry"]):
            flat = quantize(clip_ring([tuple(p) for p in ring]), closed=True)
            if len(flat) >= 6 and ring_area2(flat) != 0:
                out.append(flat)
    return out


def build_lines(fc: dict) -> list[list[int]]:
    out = []
    for feat in fc["features"]:
        for part in line_parts(feat["geometry"]):
            for run in clip_line([tuple(p) for p in part]):
                flat = quantize(run, closed=False)
                if len(flat) >= 4:
                    out.append(flat)
    return out


def sites_outside(sites: list[dict], bbox=BBOX) -> list[str]:
    x0, y0, x1, y1 = bbox
    return [
        s["code"]
        for s in sites
        if s.get("lat") is not None
        and s.get("lon") is not None
        and not (x0 <= s["lon"] <= x1 and y0 <= s["lat"] <= y1)
    ]


def main(argv: list[str] | None = None) -> int:
    web_data = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "data"
    )
    os.makedirs(web_data, exist_ok=True)

    layers = {name: load_source(*src) for name, src in SOURCES.items()}
    payload = {
        "source": f"Natural Earth 1:50m ({NE_TAG}), public domain",
        "scale": SCALE,
        "bbox": list(BBOX),
        "land": build_rings(layers["land"]),
        "lakes": build_rings(layers["lakes"]),
        "borders": build_lines(layers["borders"]),
    }
    out = os.path.join(web_data, "basemap.json")
    with open(out, "w") as fh:
        json.dump(payload, fh, separators=(",", ":"))

    npts = sum(len(r) // 2 for k in ("land", "lakes", "borders") for r in payload[k])
    print(f"wrote {out}: {os.path.getsize(out):,} bytes, {npts:,} vertices")
    for k in ("land", "lakes", "borders"):
        print(f"  {k:8} {len(payload[k]):5} parts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
