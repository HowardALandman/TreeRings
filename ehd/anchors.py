"""Calendar anchors for floating collections whose depositors published one.

A floating file numbers its rings from an arbitrary origin, so its year column
carries no calendar position of its own.  For some of them the position *is*
known - established outside the file, by radiocarbon wiggle-matching - and the
depositor wrote it into the NOAA template.  This module is the reviewed list of
those, and the check that each one still reads the way it was reviewed.

Each anchor pins one ring ordinal to one year BP.  Everything else follows,
because a floating file's internal alignment is exact: ordinal ``k`` is
``bp - (k - ordinal)`` BP, i.e. astronomical year ``1950 - bp + (k - ordinal)``.
The result is in the corpus's own convention, astronomical years (year 0 =
1 BC), which is what the Tucson files use - neth009 has a ring at year 0.

**Why a table, not a rule.**  A generic rule ("the declared BP span starts at
ordinal 1") would anchor these five and quietly anchor anything that happened to
fit it next.  A table means every calendar position the viewer draws for
subfossil wood has been read by a person, with the evidence written down here.
``apply`` then refuses to anchor unless the file still reproduces the declared
span exactly, so an archive change cannot silently move these logs.

**Where the anchor ordinal comes from.**  The declared BP span is not always the
file's full span, and the two cases are told apart by exact length agreement:

* fra053-055: the declared span equals the full measured span in length (434,
  348, 233 years), so ordinal 1 is ``First_Year``.
* brit099/100: the full spans are 413 and 453 years against declared 412 and
  418, but the *replicated* span - years covered by at least two series - is
  412 and 418 exactly, and anchoring its first ordinal to ``First_Year`` lands
  its last on ``Last_Year`` too.  Two independent exact matches, one per file,
  where the full-span reading misses by 1 and 35.  The depositors' "earliest
  year being 5224 +/-4 cal. years BP" therefore means the earliest replicated
  year; the single unreplicated rings before it (1 in brit099, 5 in brit100)
  are placed by the same offset.  Status: inferred from the length agreement,
  not stated by the depositors; either reading is inside the stated 1-sigma.

The Swiss Late Glacial files (swit195-198, swit240) are *not* here.  Their
declared span is a site-wide umbrella (all four Daettnau files declare
14237-12750 BP) rather than a per-file position, and NCEI's correlation-stats
file for swit196 confirms rings numbered 1..375 with no offset.  They stay
floating until a per-file anchor is found.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace

from .rwl import Series

BP_ORIGIN_CE = 1950


@dataclass(frozen=True)
class Anchor:
    basis: str      # "full" or "replicated": which span the declared one describes
    sigma: float    # 1-sigma uncertainty of the calendar position, years
    source: str     # the depositor's own statement of the position


# Positions and uncertainties exactly as each file's NOAA template states them;
# nothing here comes from outside the archive.
ANCHORS: dict[str, Anchor] = {
    "fra053": Anchor("full", 2.5, "First_Year 14378 cal BP; Description: 1-s age uncertainty of ca. 2.5 cal yrs"),
    "fra054": Anchor("full", 2.5, "First_Year 14090 cal BP; Description: 1-s age uncertainty of ca. 2.5 cal yrs"),
    "fra055": Anchor("full", 2.5, "First_Year 13927 cal BP; Description: 1-s age uncertainty of ca. 2.5 cal yrs"),
    "brit099": Anchor("replicated", 4, "Description: earliest year being 5224 \u00b14 cal. years BP"),
    "brit100": Anchor("replicated", 6, "Description: earliest year being 4612 \u00b16 cal. years BP"),
}


class AnchorMismatch(Exception):
    """The file no longer reproduces the declared span it was reviewed against."""


def reference_span(series: list[Series], basis: str) -> tuple[int, int]:
    """The ordinal span the declared BP span describes."""
    if basis == "full":
        return min(s.first_year for s in series), max(s.last_year for s in series)
    if basis == "replicated":
        depth: Counter[int] = Counter()
        for s in series:
            for k, v in enumerate(s.values):
                if v is not None:
                    depth[s.first_year + k] += 1
        years = [y for y, d in depth.items() if d >= 2]
        if not years:
            raise AnchorMismatch("no year is covered by two series")
        return min(years), max(years)
    raise ValueError(f"unknown anchor basis {basis!r}")


def offset(series: list[Series], meta: dict, anchor: Anchor) -> int:
    """Years to add to every ordinal to get astronomical CE.

    Raises ``AnchorMismatch`` unless the reference span, shifted, equals the
    declared BP span at *both* ends - one end fixes the offset, the other end is
    the check.
    """
    bp_first = int(float(meta["declared_first"]))
    bp_last = int(float(meta["declared_last"]))
    if bp_first <= bp_last:
        raise AnchorMismatch(f"declared span {bp_first}..{bp_last} is not in BP order")
    lo, hi = reference_span(series, anchor.basis)
    shift = BP_ORIGIN_CE - bp_first - lo
    if (hi + shift) != BP_ORIGIN_CE - bp_last:
        raise AnchorMismatch(
            f"{anchor.basis} span {lo}..{hi} ({hi - lo + 1} yr) does not fit "
            f"declared {bp_first}..{bp_last} BP ({bp_first - bp_last + 1} yr)"
        )
    return shift


def shift_series(series: list[Series], shift: int) -> list[Series]:
    return [
        replace(s, first_year=s.first_year + shift, last_year=s.last_year + shift)
        for s in series
    ]
