#!/usr/bin/env python3
"""What would a release change?  Compares web/data with the live site.

Every line of the output needs an explanation before deploying: a lost log, or
a changed site record nobody intended, is what this exists to catch.

Usage:
    python scripts/diff_payload.py [--origin URL]
"""

from __future__ import annotations

import argparse
import array
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ehd import compress  # noqa: E402
from scripts.release_facts import served  # noqa: E402
from scripts.verify_deploy import ORIGIN  # noqa: E402

SHOW = 12


def identities(index: dict, logs_bin: bytes) -> collections.Counter:
    """(site code, series id, first, last, taxon group), counted: IDs may repeat."""
    values = array.array("i")
    values.frombytes(logs_bin)
    width = len(index["fields"])
    out: collections.Counter = collections.Counter()
    for i in range(index["n_logs"]):
        r = values[i * width: (i + 1) * width]
        out[(index["sites"][r[5]]["code"], index["series_ids"][i], r[0], r[1],
             index["groups"][r[4]])] += 1
    return out


def describe(title: str, items: list) -> None:
    print(f"{title}: {len(items)}")
    for item in items[:SHOW]:
        print(f"  {item}")
    if len(items) > SHOW:
        print(f"  ... and {len(items) - SHOW} more")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--origin", default=ORIGIN)
    args = ap.parse_args(argv)

    old_index = json.loads(served(args.origin, "/data/index.json"))
    old_bin = served(args.origin, "/data/logs.bin")
    data = os.path.join(ROOT, "web", "data")
    new_index = json.loads(compress._decompress(open(os.path.join(data, "index.json"), "rb").read()))
    new_bin = compress._decompress(open(os.path.join(data, "logs.bin"), "rb").read())

    old, new = identities(old_index, old_bin), identities(new_index, new_bin)
    print(f"logs: live {old_index['n_logs']:,}, build {new_index['n_logs']:,}")
    describe("logs lost", sorted((old - new).elements()))
    added = sorted((new - old).elements())
    describe("logs added", added)
    print(f"logs added, by site: {collections.Counter(a[0] for a in added).most_common(SHOW)}")

    old_sites = {s["code"]: s for s in old_index["sites"]}
    new_sites = {s["code"]: s for s in new_index["sites"]}
    describe("sites removed", sorted(set(old_sites) - set(new_sites)))
    describe("sites added", sorted(set(new_sites) - set(old_sites)))
    describe("site records changed",
             sorted(c for c in old_sites if c in new_sites and old_sites[c] != new_sites[c]))

    print(f"years: live {old_index['year_min']}..{old_index['year_max']}, "
          f"build {new_index['year_min']}..{new_index['year_max']}")
    stats = {k: (old_index["stats"].get(k), new_index["stats"].get(k))
             for k in sorted(set(old_index["stats"]) | set(new_index["stats"]))
             if old_index["stats"].get(k) != new_index["stats"].get(k)}
    describe("stats changed", [f"{k}: {a} -> {b}" for k, (a, b) in stats.items()])
    return 0


if __name__ == "__main__":
    sys.exit(main())
