"""Two startup-order bugs in app.js, pinned against the shipped source.

1. Browsers restore a <select>'s last value on reload.  load() assumed the
   defaults, so the menu could say "Packed together" over a by-taxon drawing.
2. load() called resetView() before filling the footer.  At ~1000 px the footer
   wraps to three lines and shrinks the canvas by ~66 px, so the first view was
   fitted to a canvas that no longer existed; choosing "By taxon" then re-fitted
   it and the drawing jumped (0.01036 -> 0.00930 px/row, measured 2026-09-26).

Both were verified in a browser before and after the fix; these tests keep the
fix from being undone by a later reshuffle of load().
"""

from __future__ import annotations

import os
import re

APP_JS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "app.js"
)


def source() -> str:
    return open(APP_JS, encoding="utf-8").read()


def load_body() -> str:
    m = re.search(r"^async function load\(\) \{.*?^\}", source(), re.S | re.M)
    assert m, "load() not found in app.js"
    # Drop comments so an explanatory mention of resetView() does not count.
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", m.group(0), flags=re.S)


def test_load_takes_layout_and_era_from_the_controls():
    body = load_body()
    assert "state.mode = $('mode').value" in body
    assert "state.era = $('era').value" in body


def test_view_is_fitted_after_layout_settles():
    assert "resetView(" not in load_body()
    assert re.search(r"load\(\)\.then\(\(\) => \{ resize\(\); resetView\(\); \}\)", source())
