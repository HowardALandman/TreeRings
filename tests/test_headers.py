"""The compression in ehd.emit and the rules in web/_headers must agree.

logs.bin and index.json are written brotli-compressed under their plain names,
and `Content-Encoding: br` from _headers is the only thing that tells a browser
so.  Either half alone is a broken site: without the header the viewer gets a
compressed buffer and draws nothing; without the compression the browser tries
to brotli-decode raw geometry and the fetch fails.  Nothing in the build links
them, so they are pinned here.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ehd import compress, emit  # noqa: E402
from scripts.serve import matches, parse_headers  # noqa: E402

WEB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web"
)
RULES = parse_headers(os.path.join(WEB, "_headers"))


def headers_for(path: str) -> dict[str, str]:
    """Every header Pages would apply to `path`, in rule order."""
    out: dict[str, str] = {}
    for pattern, headers in RULES:
        if matches(pattern, path):
            out.update(headers)
    return out


def test_compressed_payloads_declare_their_encoding():
    for path in ("/data/logs.bin", "/data/index.json"):
        assert headers_for(path).get("Content-Encoding") == "br", path


def test_uncompressed_payloads_do_not():
    # The values/ shards are written as plain JSON for Cloudflare to compress
    # on the fly; claiming an encoding for them would break every sparkline.
    for path in ("/data/values/swit195.json", "/app.js", "/index.html"):
        assert "Content-Encoding" not in headers_for(path), path


def test_payload_rules_do_not_shadow_the_cache_policy():
    # Rules accumulate rather than override, so the specific /data/logs.bin
    # rule must not have cost it the no-cache from /data/*.
    for path in ("/data/logs.bin", "/data/index.json"):
        h = headers_for(path)
        assert h.get("Cache-Control") == "no-cache", path
        assert h.get("X-Content-Type-Options") == "nosniff", path


def test_brotli_round_trip():
    data = b"".join(bytes([i % 251]) * 37 for i in range(400))
    out = compress.compress(data)
    assert len(out) < len(data)
    assert compress._decompress(out) == data


def test_geometry_record_width_matches_the_viewer():
    # app.js hardcodes F = 6 and checks logs.bin's length against n_logs * F * 4;
    # adding a field to FIELDS without changing app.js would trip that check on
    # every visitor rather than here.
    assert len(emit.FIELDS) == 6
    app_js = open(os.path.join(WEB, "app.js")).read()
    assert "const F = 6;" in app_js
