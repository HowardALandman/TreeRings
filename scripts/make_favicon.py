#!/usr/bin/env python3
"""Render web/favicon.ico (and favicon.svg) from the app's own palette.

There is no image library in the venv and no need for one: the icon is
concentric rings, which is a distance-to-centre test per pixel.  Rendered 4x
and box-downsampled for antialiasing, written as PNG with zlib from stdlib,
then packed into an ICO by ffmpeg.

The rings are deliberately eccentric -- a pith off-centre is what real
ring sequences look like, and it reads better than a bullseye at 16px.

Usage:
    python scripts/make_favicon.py
"""

from __future__ import annotations

import os
import struct
import subprocess
import tempfile
import sys
import zlib

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")

# style.css dark theme: --surface-1 and --pine, plus --oak for the outer band.
BG = (0x1A, 0x1A, 0x19)
PINE = (0x12, 0xA4, 0x88)
OAK = (0xC4, 0x7A, 0x22)

SIZE = 64
SS = 4  # supersample factor
PITH = (0.48, 0.51)  # off-centre, in unit coordinates
# (outer radius, colour) bands, smallest first; radii are fractions of the icon.
# The first band whose radius reaches the pixel wins, so this reads outward
# from the pith; anything past the last band is background.
RINGS = [
    (0.07, PINE),
    (0.13, BG),
    (0.19, PINE),
    (0.26, BG),
    (0.32, PINE),
    (0.39, BG),
    (0.44, OAK),
]


def _shade(x: float, y: float) -> tuple[int, int, int]:
    dx, dy = x - PITH[0], y - PITH[1]
    # Slight anisotropy so the rings are ovals, not circles.
    r = (dx * dx * 1.18 + dy * dy) ** 0.5
    for radius, colour in RINGS:
        if r <= radius:
            return colour
    return BG


def render(size: int) -> bytes:
    """RGB bytes for a `size`x`size` icon, supersampled `SS`x."""
    big = size * SS
    hi = []
    for py in range(big):
        row = []
        for px in range(big):
            row.append(_shade((px + 0.5) / big, (py + 0.5) / big))
        hi.append(row)

    out = bytearray()
    for py in range(size):
        for px in range(size):
            acc = [0, 0, 0]
            for sy in range(SS):
                for sx in range(SS):
                    c = hi[py * SS + sy][px * SS + sx]
                    for i in range(3):
                        acc[i] += c[i]
            out.extend(a // (SS * SS) for a in acc)
    return bytes(out)


def write_png(path: str, size: int, rgb: bytes) -> None:
    raw = b"".join(
        b"\x00" + rgb[y * size * 3 : (y + 1) * size * 3] for y in range(size)
    )

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    open(path, "wb").write(png)


SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" fill="#1a1a19"/>
  <g transform="translate(28.2,33.3) scale(0.92,1)" fill="none" stroke="#12a488">
    <ellipse rx="27.5" ry="27.5" stroke="#c47a22" stroke-width="3.8"/>
    <ellipse rx="20.2" ry="20.2" stroke-width="4.5"/>
    <ellipse rx="12.5" ry="12.5" stroke-width="4.5"/>
    <circle r="4.2" fill="#12a488" stroke="none"/>
  </g>
</svg>
"""


def main() -> int:
    svg = os.path.join(WEB, "favicon.svg")
    open(svg, "w").write(SVG)

    ico = os.path.join(WEB, "favicon.ico")
    # The PNG is only ffmpeg's input, so it goes to a temp dir rather than
    # into web/, which is the deploy directory: an unreferenced file there
    # would ship to the site for no reason.
    with tempfile.TemporaryDirectory() as tmp:
        png = os.path.join(tmp, "favicon.png")
        write_png(png, SIZE, render(SIZE))
        r = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-i", png, "-vf", "scale=32:32",
             "-y", ico],
            capture_output=True,
        )
    if r.returncode:
        sys.stderr.write(r.stderr.decode())
        return 1

    for p in (ico, svg):
        print(f"  {os.path.basename(p):<14} {os.path.getsize(p):>7,} B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
