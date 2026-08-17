"""Greedy row packing for log rectangles on a shared time axis.

Logs are sorted by end year, latest first, then first-fit into rows: each log
goes into the topmost row whose leftmost occupied year still sits clear of it.
This is first-fit interval graph colouring; because the input is sorted by right
endpoint, the row count lands at the maximum overlap depth, which is optimal.

The sort is fully deterministic (end year, then start year, then id) so that a
rebuild produces a byte-identical layout - a layout that shifts between runs
would make visual regressions impossible to spot.
"""

from __future__ import annotations

from dataclasses import dataclass

# Blank years left between two logs sharing a row, so adjacent rectangles read
# as separate bars rather than merging into one.
DEFAULT_GAP = 2


@dataclass
class Placed:
    key: str
    start: int
    end: int
    row: int
    group: str = ""


def pack(
    items: list[tuple[str, int, int]],
    gap: int = DEFAULT_GAP,
    group: str = "",
) -> list[Placed]:
    """Pack ``(key, start_year, end_year)`` triples into non-overlapping rows.

    Returns the placements in sorted (drawing) order.
    """
    ordered = sorted(items, key=lambda t: (-t[2], -t[1], t[0]))

    # rows[i] is the earliest (leftmost) year currently occupied in row i.
    # It only ever decreases, because we place logs from latest to earliest.
    rows: list[int] = []
    placed: list[Placed] = []

    for key, start, end in ordered:
        target = -1
        for i, leftmost in enumerate(rows):
            if leftmost - gap > end:
                target = i
                break
        if target < 0:
            rows.append(start)
            target = len(rows) - 1
        else:
            rows[target] = start
        placed.append(Placed(key=key, start=start, end=end, row=target, group=group))

    return placed


def pack_grouped(
    groups: dict[str, list[tuple[str, int, int]]],
    gap: int = DEFAULT_GAP,
) -> tuple[list[Placed], dict[str, int]]:
    """Pack each group independently, e.g. pines above a baseline and oaks below.

    Returns the placements plus each group's row count, so the caller can stack
    or mirror the groups on screen.
    """
    out: list[Placed] = []
    heights: dict[str, int] = {}
    for name in sorted(groups):
        placed = pack(groups[name], gap=gap, group=name)
        heights[name] = (max((p.row for p in placed), default=-1)) + 1
        out.extend(placed)
    return out, heights


def find_overlaps(placed: list[Placed], gap: int = DEFAULT_GAP) -> list[tuple[str, str]]:
    """Return every pair of rectangles that overlap within a row.

    The packing is only correct if this comes back empty, so it is checked
    rather than assumed.
    """
    by_row: dict[tuple[str, int], list[Placed]] = {}
    for p in placed:
        by_row.setdefault((p.group, p.row), []).append(p)

    bad: list[tuple[str, str]] = []
    for items in by_row.values():
        items.sort(key=lambda p: p.start)
        for a, b in zip(items, items[1:]):
            # Rectangles are inclusive of both endpoints.
            if b.start - gap <= a.end:
                bad.append((a.key, b.key))
    return bad


def row_count(placed: list[Placed]) -> int:
    return max((p.row for p in placed), default=-1) + 1
