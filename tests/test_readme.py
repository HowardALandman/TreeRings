"""The README states the numbers recorded for the live build.

They are hand-written prose, so they drift: on 2026-11-01 the README still gave
73,390 logs against 123,370 live.  Each sentence is required exactly, because a
bare number could be satisfied by history the README rightly keeps.  When this
fails after a release, edit the README, as docs/RELEASE.md says.
"""

import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

README = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
# Line wrapping in the prose is not a fact.
FLAT = " ".join(README.split())
RECORD = json.load(open(os.path.join(ROOT, "docs", "release-facts.json"), encoding="utf-8"))
P = RECORD["payload"]
LOAD = RECORD["first_load"]
V = RECORD["validation"]


def span() -> str:
    assert P["first_year"] <= 0 < P["last_year"]
    return f"{1 - P['first_year']} BC – {P['last_year']} CE"


def sources() -> str:
    parts = [f"{P['by_source']['itrdb']:,} ITRDB", f"{P['by_source']['pangaea']:,} PANGAEA"]
    if P["by_source"]["zenodo"]:
        parts.append(f"{P['by_source']['zenodo']:,} Zenodo")
    return ", ".join(parts)


def page_bytes() -> int:
    return sum(LOAD["by_path"][p] for p in ("/", "/app.js", "/style.css"))


EXPECTED = [
    f"**{P['n_logs']:,} logs · {P['n_sites']:,} sites · {span()}** ({sources()}).",
    f"{P['alive']['5000 BC']} logs alive in 5000 BC, {P['alive']['1 CE']} at 1 CE, and "
    f"{P['alive']['1971 CE']:,} in 1971.",
    f"~{round(P['unified_rows'], -3):,}-row wedge",
    f"No log is alive between {P['hole']['last_alive_before']} and "
    f"{P['hole']['first_alive_after']}",
    f"first load is {LOAD['total']:,} bytes: `logs.bin` {LOAD['by_path']['/data/logs.bin']:,}, "
    f"`index.json` {LOAD['by_path']['/data/index.json']:,}, and the page, `app.js` and "
    f"`style.css` {page_bytes():,}",
    f"calendar-dated by the depositors ({P['dating_logs']['absolute']:,})",
    f"carried with its uncertainty ({P['dating_logs']['anchored']}, across "
    f"{P['dating_sites']['anchored']} collections",
    f"no declared span exists to check against ({P['dating_logs']['unverified']}, across "
    f"{P['dating_sites']['unverified']} collections)",
    f"the data contradicts ({P['dating_logs']['disputed']}, across "
    f"{P['dating_sites']['disputed']} collections",
    f"not calendar years ({P['floating_withheld']}, across",
    f"never drawn ({P['withdrawn_withheld']:,} logs, {P['withdrawn_studies']} studies)",
    f"**{V['agreement']} span agreement with dplR across {V['compared']:,} series**",
    f"reads {V['only_ours']:,} series dplR cannot (run {V['date']}, dplR {V['dplr']})",
]


@pytest.mark.parametrize("sentence", EXPECTED)
def test_readme_states_the_recorded_number(sentence):
    assert sentence in FLAT, f"README should say: {sentence}"


def test_dating_classes_add_up_to_the_logs_drawn():
    assert sum(P["dating_logs"].values()) == P["n_logs"]
    assert sum(P["by_source"].values()) == P["n_logs"]


def test_first_load_total_is_the_sum_of_its_parts():
    assert sum(LOAD["by_path"].values()) == LOAD["total"]
