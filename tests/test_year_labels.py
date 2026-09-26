"""The viewer's year labels, run under node against the shipped app.js.

The data is in astronomical years (year 0 = 1 BC; neth009 has a ring measured in
year 0).  The viewer used to print -y as "y BC", which put every BC label on the
site one year late and printed year 0 as "0 CE".
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

import pytest

APP_JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "app.js")


def function_source(name: str) -> str:
    src = open(APP_JS, encoding="utf-8").read()
    m = re.search(rf"^function {name}\(.*?^}}", src, re.S | re.M)
    assert m, f"{name} not found in app.js"
    return m.group(0)


def run(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    prog = function_source("fmtYear") + "\n" + function_source("tickYear") + \
        f"\nprocess.stdout.write(JSON.stringify({expr}));"
    return json.loads(subprocess.run([node, "-e", prog], capture_output=True,
                                     text=True, check=True).stdout)


@pytest.mark.parametrize("astro,label", [
    (1, "1 CE"),
    (0, "1 BC"),
    (-1, "2 BC"),
    (-5407, "5408 BC"),      # swed334, the oldest calendar-dated collection
    (-12428, "12429 BC"),    # fra053 ring 1 = 14378 cal BP
    (2023, "2023 CE"),
])
def test_fmt_year(astro, label):
    assert run(f"fmtYear({astro})") == label


@pytest.mark.parametrize("historical,label", [
    (-100, "100 BC"), (-10000, "10000 BC"), (0, "1 CE"), (500, "500 CE"),
])
def test_ticks_land_on_round_labels(historical, label):
    assert run(f"fmtYear(tickYear({historical}))") == label


def test_bp_conversion_agrees_with_labels():
    # 1950 BP is year 0 = 1 BC; 1949 BP is 1 CE.
    assert run(f"[fmtYear(1950 - 1950), fmtYear(1950 - 1949)]") == ["1 BC", "1 CE"]
