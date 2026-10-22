"""Row packing: overlap-free, optimal, deterministic, and flush on the left.

Optimality is checked against an independent count - the deepest point of
the intervals widened by the gap - not against the packer itself.
"""

from __future__ import annotations

import random

from ehd.pack import find_overlaps, pack, row_count


def depth(items, gap):
    # Two logs conflict when b.start - gap <= a.end, i.e. when [s, e + gap]
    # intervals intersect; the deepest point is a lower bound on rows.
    best = 0
    for y in range(min(s for _, s, _ in items), max(e for _, _, e in items) + gap + 1):
        best = max(best, sum(1 for _, s, e in items if s <= y <= e + gap))
    return best


def random_logs(rng, n):
    out = []
    for k in range(n):
        s = rng.randint(-300, 300)
        out.append((f"log{k}", s, s + rng.randint(0, 120)))
    return out


def test_random_corpora_are_overlap_free_and_optimal():
    rng = random.Random(20261022)
    for trial in range(200):
        items = random_logs(rng, rng.randint(1, 60))
        gap = rng.choice([0, 1, 2, 5])
        placed = pack(items, gap=gap)
        assert find_overlaps(placed, gap=gap) == []
        assert row_count(placed) == depth(items, gap), trial


def test_row_starts_never_move_left_going_down():
    # The first log in each row starts no earlier than the row above's: the
    # band's left edge is a monotone curve, which is the point of the order.
    rng = random.Random(7)
    placed = pack(random_logs(rng, 500))
    first = {}
    for p in placed:
        first[p.row] = min(first.get(p.row, p.start), p.start)
    starts = [first[r] for r in range(row_count(placed))]
    assert starts == sorted(starts)


def test_gap_is_respected_at_the_boundary():
    # Default gap 2: a log ending in 10 leaves 11 and 12 blank.
    assert [p.row for p in pack([("a", 0, 10), ("b", 13, 20)])] == [0, 0]
    assert [p.row for p in pack([("a", 0, 10), ("b", 12, 20)])] == [0, 1]


def test_layout_does_not_depend_on_input_order():
    rng = random.Random(3)
    items = random_logs(rng, 200) + [("tie1", 0, 50), ("tie2", 0, 50)]
    want = {p.key: p.row for p in pack(items)}
    for _ in range(5):
        rng.shuffle(items)
        assert {p.key: p.row for p in pack(items)} == want
