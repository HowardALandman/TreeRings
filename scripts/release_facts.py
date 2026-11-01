#!/usr/bin/env python3
"""The numbers a release states, measured from its payload.

`docs/release-facts.json` records them for the build that is live.  README
sentences are checked against that record by `tests/test_readme.py`, so the
README can only drift by failing a test, and the record itself is checked
against the live site here.  See docs/RELEASE.md.

Usage:
    python scripts/release_facts.py                  # print facts of web/data
    python scripts/release_facts.py --origin URL     # print facts of a live site
    python scripts/release_facts.py --check          # live site == the record?
    python scripts/release_facts.py --write          # record the live site
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
from scripts.verify_deploy import ORIGIN, decoded, fetch  # noqa: E402

RECORD = os.path.join(ROOT, "docs", "release-facts.json")
FIRST_LOAD = ("/", "/app.js", "/style.css", "/data/logs.bin", "/data/index.json")
N_FIELDS = 6


def bc_or_ce(year: int) -> str:
    """Astronomical year as a label: year 0 is 1 BC."""
    return f"{1 - year} BC" if year <= 0 else f"{year} CE"


def alive_counts(spans: list[tuple[int, int]]) -> dict[int, int]:
    """Logs alive in each year from the first ring to the last."""
    delta: collections.Counter = collections.Counter()
    for first, last in spans:
        delta[first] += 1
        delta[last + 1] -= 1
    alive, count = {}, 0
    for year in range(min(delta), max(delta)):
        count += delta[year]
        alive[year] = count
    return alive


def facts_of(index: dict, logs_bin: bytes) -> dict:
    """Everything here comes from the payload, so a site can be measured as served."""
    values = array.array("i")
    values.frombytes(logs_bin)
    n = index["n_logs"]
    if len(values) != n * N_FIELDS:
        raise ValueError(f"logs.bin has {len(values)} ints for {n} logs")
    rows = [values[i * N_FIELDS: (i + 1) * N_FIELDS] for i in range(n)]
    spans = [(r[0], r[1]) for r in rows]
    alive = alive_counts(spans)
    empty = [y for y in sorted(alive) if alive[y] == 0]
    # One contiguous hole is what the prose describes; more must fail loudly.
    if empty and empty[-1] - empty[0] + 1 != len(empty):
        raise ValueError("coverage has more than one hole: rewrite the README's account")
    sites = index["sites"]
    dating = collections.Counter(sites[r[5]]["dating"] for r in rows)
    dating_sites = collections.Counter(s["dating"] for s in sites)
    stats = index["stats"]
    pangaea = stats.get("pangaea_plotted", 0)
    zenodo = stats.get("zenodo_plotted", 0)
    return {
        "n_logs": n,
        "n_sites": len(sites),
        "first_year": index["year_min"],
        "last_year": index["year_max"],
        "unified_rows": index["unified_rows"],
        "by_source": {"itrdb": n - pangaea - zenodo, "pangaea": pangaea, "zenodo": zenodo},
        "alive": {"5000 BC": alive[-4999], "1 CE": alive[1], "1971 CE": alive[1971]},
        # The last and first logs either side of the hole, as the prose names them.
        "hole": {
            "last_alive_before": bc_or_ce(empty[0] - 1),
            "first_alive_after": bc_or_ce(empty[-1] + 1),
            "empty_years": len(empty),
        } if empty else None,
        "dating_logs": dict(sorted(dating.items())),
        "dating_sites": dict(sorted(dating_sites.items())),
        "floating_withheld": stats["logs_floating"],
        "withdrawn_withheld": stats["logs_withdrawn"],
        "withdrawn_studies": stats["sites_withdrawn"],
    }


def local_facts() -> dict:
    data = os.path.join(ROOT, "web", "data")
    index = compress._decompress(open(os.path.join(data, "index.json"), "rb").read())
    logs = compress._decompress(open(os.path.join(data, "logs.bin"), "rb").read())
    return facts_of(json.loads(index), logs)


def served(origin: str, path: str) -> bytes:
    status, headers, body = fetch(origin + path)
    if status != 200:
        raise OSError(f"{origin}{path}: HTTP {status}")
    return decoded(headers, body)


def live_facts(origin: str) -> dict:
    return facts_of(json.loads(served(origin, "/data/index.json")),
                    served(origin, "/data/logs.bin"))


def first_load(origin: str) -> dict:
    """Bytes on the wire, as a browser asks for them."""
    sizes = {}
    for path in FIRST_LOAD:
        status, _, body = fetch(origin + path, accept_encoding="br, gzip, deflate")
        if status != 200:
            raise OSError(f"{origin}{path}: HTTP {status}")
        sizes[path] = len(body)
    return {"total": sum(sizes.values()), "by_path": sizes}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--origin", help="measure this site instead of web/data")
    ap.add_argument("--check", action="store_true", help="compare the live site with the record")
    ap.add_argument("--write", action="store_true", help="record the live site's facts")
    args = ap.parse_args(argv)

    if args.check or args.write:
        origin = args.origin or ORIGIN
        facts = live_facts(origin)
        record = json.load(open(RECORD)) if os.path.exists(RECORD) else {}
        if args.check:
            if facts != record.get("payload"):
                print(f"MISMATCH: {origin} against {RECORD}")
                for key in sorted(set(facts) | set(record.get("payload", {}))):
                    if facts.get(key) != record.get("payload", {}).get(key):
                        print(f"  {key}: live {facts.get(key)}, "
                              f"record {record.get('payload', {}).get(key)}")
                return 1
            print(f"OK: {origin} matches the record ({facts['n_logs']:,} logs)")
            return 0
        record["payload"] = facts
        record["first_load"] = first_load(origin)
        record.setdefault("validation", {})
        with open(RECORD, "w") as fh:
            json.dump(record, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"wrote {RECORD}; now update `validation` by hand if ehd.validate was rerun")
        return 0

    facts = live_facts(args.origin) if args.origin else local_facts()
    print(json.dumps(facts, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
