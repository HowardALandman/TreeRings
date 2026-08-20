"""Brotli compression for the payloads the viewer loads on first paint.

Cloudflare compresses static assets on the fly, but two things about that are
wrong for this site.  Its allowlist is keyed on content type and excludes
`application/octet-stream`, so `logs.bin` -- 84% of first load -- was shipped
raw.  And where it does compress, it is tuned for speed rather than ratio: it
returns `index.json` at 345,660 B where `brotli -q 11` gets it to 254,711 B.

So both files are pre-compressed here at maximum quality and served with an
explicit `Content-Encoding: br` from `web/_headers`.  Nothing downstream
changes: `Content-Encoding` is unwrapped at the HTTP layer, so `app.js` still
sees the original bytes from `arrayBuffer()` and `json()`.

Either the `brotli` Python module (`uv pip install brotli`) or the `brotli`
command-line tool will do.  The module is preferred; the CLI keeps the pipeline
working on a checkout that has not installed it.
"""

from __future__ import annotations

import shutil
import subprocess

QUALITY = 11  # maximum; this runs once per pipeline run, so time is free

try:  # pragma: no cover - which branch runs depends on the environment
    import brotli as _brotli
except ImportError:
    _brotli = None


def backend() -> str | None:
    """Name of the compressor that will be used, or None if there isn't one."""
    if _brotli is not None:
        return "brotli module"
    if shutil.which("brotli"):
        return "brotli CLI"
    return None


def _cli(args: list[str], data: bytes) -> bytes:
    proc = subprocess.run(
        ["brotli", *args], input=data, capture_output=True, check=True
    )
    return proc.stdout


def _compress(data: bytes) -> bytes:
    if _brotli is not None:
        return _brotli.compress(data, quality=QUALITY)
    return _cli([f"-q{QUALITY}", "-c"], data)


def _decompress(data: bytes) -> bytes:
    if _brotli is not None:
        return _brotli.decompress(data)
    return _cli(["-d", "-c"], data)


def compress(data: bytes) -> bytes:
    """Compress `data`, verifying that it decompresses back to exactly `data`.

    A silently corrupt payload here would reach the browser as garbage
    geometry, which is far harder to diagnose than a failed build, so the
    round trip is checked every time rather than trusted.
    """
    if backend() is None:
        raise RuntimeError(
            "no brotli available: `uv pip install brotli`, or install the "
            "brotli command-line tool (`brew install brotli`)"
        )
    out = _compress(data)
    if _decompress(out) != data:
        raise RuntimeError(
            f"brotli round trip did not reproduce the input "
            f"({len(data)} bytes in, {len(out)} bytes compressed)"
        )
    return out


def write(path: str, data: bytes) -> tuple[int, int]:
    """Write `data` to `path` brotli-compressed.  Returns (raw, compressed)."""
    out = compress(data)
    with open(path, "wb") as fh:
        fh.write(out)
    return len(data), len(out)
