"""PANGAEA's tree-ring records: parsing the public metadata, and what is drawn.

Record shapes are taken from the live index (2026-10-24).
"""

from __future__ import annotations

from ehd import corpus, pangaea


def hit(_id, title, comments, *, author="Hofmann, Jutta", project="HISTRA",
        label="HOF11557", place="Lupburg, Bavaria, Southern Germany",
        lat=49.15, lon=11.75, login=3):
    xml = (f"<md:title>{title}</md:title>"
           + "".join(f"<md:comment>{c}</md:comment>" for c in comments)
           + f'<md:event id="e1"><md:label>{label}</md:label>'
           + f'<md:location id="l1"><md:name>{place}</md:name></md:location>'
           + '<md:campaign id="c1"><md:label>TreeRings_SouthGermany</md:label></md:campaign>'
           + "</md:event>"
           + "<md:license><md:label>UNKNOWN</md:label><md:name>Licensing unknown: "
             "Please contact principal investigator/authors</md:name></md:license>")
    return {"_id": str(_id), "_source": {
        "URI": f"https://doi.org/10.1594/PANGAEA.{_id}", "agg-author": author,
        "agg-project": project, "meanPosition": {"lat": lat, "lon": lon},
        "sp-loginOption": login, "xml": xml}}


def test_hohenheim_span_line():
    r = pangaea.parse_record(hit(657234,
        "Tree-ring width of Picea abies (Karsten) from historical object sample HOF11557-2",
        ["Species PCAB; No of rings 57; Begin 1717; End 1773"]))
    assert (r["first"], r["last"], r["n_rings"], r["species_code"]) == (1717, 1773, 57, "PCAB")
    assert (r["object"], r["sample"], r["kind"]) == ("HOF11557", "HOF11557-2", "historical object")
    assert r["place"] == "Lupburg, Bavaria, Southern Germany"
    assert r["license"].startswith("Licensing unknown")


def test_pressler_span_is_in_a_later_comment():
    # The first comment is the building; reading only it found no span in
    # 4,836 of Preßler's records.
    r = pangaea.parse_record(hit(148064,
        "Tree-ring width of Quercus species from historical object sample 5575B/02A, Netherlands, Diever",
        ["Building, Haupthaus",
         "Species: Quercus species; No of rings: 56; first year: 1664; end year: 1720; Pith: not applicable"],
        author="Preßler, Erhard", label="5575B"))
    assert (r["first"], r["last"], r["sample"], r["object"]) == (1664, 1720, "5575B/02A", "5575B")


def test_tree_death_year_wording():
    r = pangaea.parse_record(hit(1, "Tree-ring width of Quercus species from historical object sample 1B/01A, X",
                                 ["Species: Quercus species; No of rings: 140; first year: 1326; tree-death year: 1466"],
                                 author="Preßler, Erhard", label="1B"))
    assert (r["first"], r["last"]) == (1326, 1466)


def test_floating_is_recognised():
    r = pangaea.parse_record(hit(605005, "Tree-ring width of Pinus sylvestris (von Linné) of subfossil tree sample HOH2600-1050",
                                 ["Species PISY; No of rings 180; Begin 1792; End 1881; Data are shown on a "
                                  "relative timescale as the chronology is still floating."],
                                 author="Friedrich, Michael"))
    assert r["floating"]


def rec(_id, first, last, **kw):
    base = {"id": str(_id), "doi": f"10.1594/PANGAEA.{_id}", "author": "Hofmann, Jutta",
            "project": "HISTRA", "first": first, "last": last, "n_rings": None,
            "floating": False, "lat": 49.0, "lon": 11.0, "species_code": "QUSP",
            "species_name": "Quercus species", "object": "HOF1", "sample": f"HOF1-{_id}",
            "place": "Somewhere", "kind": "historical object", "elevation": None,
            "license": "restricted"}
    base.update(kw)
    return base


def test_every_exclusion_is_counted():
    recs = [rec(1, 1500, 1550),
            rec(2, 1500, 1550, author="Schweingruber, Fritz Hans"),
            rec(3, None, None),
            rec(4, 0, 0),
            rec(5, 1776, 1118),
            rec(6, 1201, 1300, floating=True),
            rec(7, 1500, 1550, lat=22.8, lon=5.5),
            rec(8, 1500, 1550, sample="HOF1-1")]  # same sample as id 1
    logs, report = pangaea.build_logs(recs)
    assert [log.series_id for log in logs] == ["HOF1-1"]
    assert sum(report.values()) == len(recs)
    assert report["duplicate of ITRDB (Schweingruber)"] == 1
    assert report["same sample deposited twice"] == 1
    assert logs[0].values == [] and logs[0].restricted and logs[0].source == "PANGAEA"


def test_pressler_spans_carry_the_note():
    logs, _ = pangaea.build_logs([rec(1, 1664, 1720, author="Preßler, Erhard")])
    assert logs[0].span_note == pangaea.PRESSLER_NOTE


def itrdb(site, first, last, lat=49.0, lon=11.0, genus="Quercus"):
    return corpus.Log(key=f"{site}/{first}", site=site, series_id=str(first), first_year=first,
                      last_year=last, n_measured=1, values=[1], variant="", genus=genus,
                      lat=lat, lon=lon)


def test_an_object_matching_an_itrdb_site_three_times_is_dropped():
    recs = [rec(i, 1500 + i, 1600 + i) for i in range(1, 5)]
    sites = [itrdb("germ069", 1500 + i, 1600 + i) for i in range(1, 4)]
    logs, report = pangaea.build_logs(recs, itrdb_logs=sites)
    assert [log.first_year for log in logs] == [1504]
    assert report["same timbers as an ITRDB site"] == 3


def test_a_single_match_is_chance_and_kept():
    recs = [rec(i, 1500 + i, 1600 + i) for i in range(1, 5)]
    logs, _ = pangaea.build_logs(recs, itrdb_logs=[itrdb("germ1", 1501, 1601)])
    assert len(logs) == 4


def test_a_match_needs_genus_and_place():
    recs = [rec(i, 1500 + i, 1600 + i) for i in range(1, 4)]
    far = [itrdb("x", 1500 + i, 1600 + i, lat=55.0) for i in range(1, 4)]
    pine = [itrdb("y", 1500 + i, 1600 + i, genus="Pinus") for i in range(1, 4)]
    assert len(pangaea.build_logs(recs, itrdb_logs=far + pine)[0]) == 3
