"""web/data/values/ must hold exactly the shards of the sites in the build.

emit overwrites shards in place, so before stale_shards() a site that left the
build kept its old shard and was deployed with everything else - which is how
the 25 studies NCEI withdrew were still being served after the 2026-10-18
rebuild withheld them from the index.
"""

from __future__ import annotations

import json
import os

import pytest

from ehd.emit import stale_shards

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


def test_only_unwritten_json_shards_are_stale(tmp_path):
    for name in ("alb001.json", "neth020.json", "notes.txt"):
        (tmp_path / name).write_text("{}")
    assert stale_shards(str(tmp_path), {"alb001"}) == ["neth020.json"]


def test_built_shards_match_the_index_exactly():
    path = os.path.join(WEB, "data", "index.json")
    if not os.path.exists(path):
        pytest.skip("web/data not built; run python -m ehd.emit")
    blob = open(path, "rb").read()
    if not blob.lstrip().startswith(b"{"):
        blob = pytest.importorskip("brotli").decompress(blob)
    want = {s["code"].lower() + ".json" for s in json.loads(blob)["sites"]}
    have = set(os.listdir(os.path.join(WEB, "data", "values")))
    assert have == want, f"extra {sorted(have - want)}, missing {sorted(want - have)}"
