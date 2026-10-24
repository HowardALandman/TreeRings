"""Harvest PANGAEA's tree-ring-width datasets: public metadata only.

PANGAEA holds ~53,000 single-timber tree-ring-width datasets, nearly all from
German dendrochronology laboratories (Hofmann, Bleyer, Friedrich/Hohenheim,
Preßler).  Their ring widths are access-restricted; their public metadata is
not, and it carries what a timeline bar needs: species, coordinates and the
dated first and last ring.  Howard's decision (2026-10-24): draw these from
the public metadata and mark them restricted.  See docs/data-survey.md.

Source: PANGAEA's Elasticsearch index (``ws.pangaea.de/es``), paged with the
scroll API.  Each raw page is saved as returned, so parsing can be redone and
audited without re-harvesting.  Counts are checked against the index's own
total, and every comment line that does not parse is counted and shown.

Usage:
    python -m ehd.pangaea            # harvest (resumes nothing; ~110 requests)
    python -m ehd.pangaea --parse    # re-parse the saved pages only
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys
import urllib.request

from . import config, fetch

ES = "https://ws.pangaea.de/es/pangaea/panmd/_search"
ES_SCROLL = "https://ws.pangaea.de/es/_search/scroll"
QUERY = '"Tree ring width"'
PAGE = 500
FIELDS = ["URI", "agg-author", "agg-project", "meanPosition", "minElevation",
          "sp-loginOption", "sp-dataStatus", "nDataPoints", "xml"]


def _post(url: str, body: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": fetch.USER_AGENT})
    with urllib.request.urlopen(req, timeout=fetch.TIMEOUT) as resp:
        return json.load(resp)


def raw_dir() -> str:
    return config.path(config.RAW, "pangaea", "treering")


def harvest() -> int:
    out = raw_dir()
    for old in glob.glob(os.path.join(out, "page-*.json")):
        os.remove(old)  # a harvest is a snapshot; never mix two
    doc = _post(ES + "?scroll=5m", {
        "size": PAGE, "_source": FIELDS,
        "query": {"query_string": {"query": QUERY}},
        "sort": ["_doc"],
    })
    total = doc["hits"]["total"]
    n, page = 0, 0
    while doc["hits"]["hits"]:
        with open(os.path.join(out, f"page-{page:04d}.json"), "w") as fh:
            json.dump(doc["hits"]["hits"], fh, ensure_ascii=False)
        n += len(doc["hits"]["hits"])
        page += 1
        if page % 20 == 0:
            print(f"  {n}/{total}", flush=True)
        doc = _post(ES_SCROLL, {"scroll": "5m", "scroll_id": doc["_scroll_id"]})
    print(f"harvested {n} of {total} reported, in {page} pages -> {out}")
    if n != total:
        # A short scroll looks exactly like a complete one downstream.
        raise RuntimeError(f"scroll returned {n} records but the index reports {total}")
    return n


# --- parsing ----------------------------------------------------------------

def _tag(xml: str, tag: str) -> str:
    m = re.search(rf"<md:{tag}\b[^>]*>(.*?)</md:{tag}>", xml, re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip() if m else ""


def _tags(xml: str, tag: str) -> list[str]:
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m)).strip()
            for m in re.findall(rf"<md:{tag}\b[^>]*>(.*?)</md:{tag}>", xml, re.S)]


# Hofmann, Bleyer, Friedrich: "Species PISY; No of rings 57; Begin 1717; End 1773"
_SPAN_A = re.compile(r"Begin\s*:?\s*(-?\d+)\s*;\s*End\s*:?\s*(-?\d+)", re.I)
# Preßler: "first year: 1326; tree-death year: 1466" or "...; end year: 1525"
_SPAN_B = re.compile(r"first year\s*:\s*(-?\d+)\s*;\s*(?:end|tree-death) year\s*:\s*(-?\d+)", re.I)
_SPECIES_CODE = re.compile(r"Species\s*:?\s*([A-Z]{4})\b")
_TITLE_SPECIES = re.compile(r"Tree-ring width of (.+?) (?:from|of) ")
_RINGS = re.compile(r"No of rings\s*:?\s*(\d+)", re.I)


def parse_record(hit: dict) -> dict:
    s = hit["_source"]
    xml = s.get("xml") or ""
    # Preßler's records carry several comments ("Building, Haupthaus", then
    # the species-and-span line); reading only the first missed every span.
    comment = "; ".join(_tags(xml, "comment"))
    title = _tag(xml, "title")
    span = _SPAN_A.search(comment) or _SPAN_B.search(comment)
    pos = s.get("meanPosition") or {}
    rings = _RINGS.search(comment)
    code = _SPECIES_CODE.search(comment)
    tsp = _TITLE_SPECIES.search(title)
    floating = bool(re.search(r"floating|relative time ?scale", comment, re.I))
    ev = re.search(r"<md:event\b.*?</md:event>", xml, re.S)
    ev = ev.group(0) if ev else ""
    kind = re.search(r"(historical object|living tree|subfossil tree) samples?\b", title)
    return {
        "id": hit["_id"],
        "doi": (s.get("URI") or "").replace("https://doi.org/", ""),
        "author": s.get("agg-author") if isinstance(s.get("agg-author"), str)
                  else "; ".join(s.get("agg-author") or []),
        "project": s.get("agg-project"),
        "data_xml": bool(re.search(r"documentation/TreeRing/data/", xml)),
        "title": title,
        "comment": comment,
        "species_code": code.group(1) if code else "",
        "species_name": tsp.group(1) if tsp else "",
        "first": int(span.group(1)) if span else None,
        "last": int(span.group(2)) if span else None,
        "n_rings": int(rings.group(1)) if rings else None,
        "floating": floating,
        "undated": "not determined" in comment.lower(),
        "object": _tag(ev, "label"),
        "place": _tag(re.search(r"<md:location\b.*?</md:location>", ev, re.S).group(0)
                      if "<md:location" in ev else "", "name"),
        "campaign": _tag(re.search(r"<md:campaign\b.*?</md:campaign>", ev, re.S).group(0)
                         if "<md:campaign" in ev else "", "label"),
        "sample": (re.search(r"sample (\S+?),? ", title + " ") or re.search(r"sample (\S+)$", title)
                   or re.search(r"(\S+)$", title)).group(1).rstrip(","),
        "kind": kind.group(1) if kind else "",
        "lat": pos.get("lat"), "lon": pos.get("lon"),
        "elevation": s.get("minElevation"),
        "login_option": s.get("sp-loginOption"),
        # The readable name only: the label ("UNKNOWN") is a code.
        "license": _tag(re.search(r"<md:license\b.*?</md:license>", xml, re.S).group(0)
                        if "<md:license" in xml else "", "name"),
        "n_points": s.get("nDataPoints"),
    }


def parse() -> list[dict]:
    pages = sorted(glob.glob(os.path.join(raw_dir(), "page-*.json")))
    recs = [parse_record(h) for p in pages for h in json.load(open(p))]
    ids = [r["id"] for r in recs]
    if len(ids) != len(set(ids)):
        raise RuntimeError(f"{len(ids) - len(set(ids))} duplicate ids across pages")
    out = config.path(config.INTERIM, "pangaea_treering.json")
    with open(out, "w") as fh:
        json.dump(recs, fh, ensure_ascii=False)
    report(recs)
    print(f"-> {out}")
    return recs


def report(recs: list[dict]) -> None:
    c = collections.Counter
    spanned = [r for r in recs if r["first"] is not None]
    print(f"{len(recs)} records; {len(spanned)} with a parsed span "
          f"({sum(r['floating'] for r in spanned)} of them floating); "
          f"{sum(r['undated'] for r in recs)} 'not determined'")
    bad = [r for r in spanned if r["last"] < r["first"]
           or (r["n_rings"] and r["last"] - r["first"] + 1 != r["n_rings"])]
    print(f"  span inconsistent with itself or with 'No of rings': {len(bad)}")
    for r in bad[:5]:
        print("    ", r["doi"], r["comment"][:100])
    print("  login option:", dict(c(r["login_option"] for r in recs)))
    print("  authors:", c(r["author"] for r in recs).most_common(8))
    print("  no position:", sum(r["lat"] is None for r in recs))
    unparsed = [r for r in recs if r["first"] is None and not r["undated"]]
    print(f"  no span and not 'not determined': {len(unparsed)}")
    for k, v in c(r["comment"][:60] for r in unparsed).most_common(12):
        print(f"    {v:6}  {k!r}")


# --- logs for the build -----------------------------------------------------

# Werner Schweingruber's open PANGAEA series are his ITRDB network again
# (2026-10-24: swit131 and roma004 match sample for sample, span for span; 95%
# of all match on span and place).  Importing them would double-count.
DUPLICATES_OF_ITRDB = re.compile(r"Schweingruber", re.I)

# Preßler's spans are one year longer than his own ring counts in 3,409 of
# 3,422 records; which end is off cannot be told without the ring widths.
PRESSLER_NOTE = ("Depositor's span is one year longer than its ring count, "
                 "as for nearly all of this laboratory's records; one end may be off by a year.")

RESTRICTED_NOTE = ("Ring widths are access-restricted by the depositor; this bar is "
                   "drawn from the record's public metadata (species, place, dated span).")


# An object and an ITRDB site are the same timbers when at least this many of
# their spans match exactly, with genus and place agreeing.  2026-10-24: ITRDB
# germ069 (Wilson, "Regensburg Dom Historical Timbers") is 22 of Hofmann's 83
# Regensburg samples (HOF12184), span for span; ~90 such matches in all
# against ~7 expected by chance, which shows up as isolated single matches
# between unrelated objects and sites.
SAME_TIMBERS_MIN_MATCHES = 3
SAME_PLACE_DEG = 0.2


def itrdb_duplicates(logs: list, itrdb_logs: list) -> set[str]:
    """Keys of PANGAEA logs that are ITRDB logs again; the ITRDB copy, which
    carries ring widths, is the one kept."""
    by_span: dict[tuple[int, int], list] = collections.defaultdict(list)
    for x in itrdb_logs:
        if x.lat is not None and x.lon is not None:
            by_span[(x.first_year, x.last_year)].append(x)
    pairs: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for log in logs:
        for x in by_span.get((log.first_year, log.last_year), ()):
            if (x.genus == log.genus and abs(x.lat - log.lat) < SAME_PLACE_DEG
                    and abs(x.lon - log.lon) < SAME_PLACE_DEG):
                pairs[(log.site, x.site)].append(log.key)
    return {k for keys in pairs.values() if len(keys) >= SAME_TIMBERS_MIN_MATCHES for k in keys}


def build_logs(recs: list[dict] | None = None, itrdb_logs: list | None = None):
    """``(logs, report)``: plottable PANGAEA logs and a count of every exclusion."""
    from . import corpus, region  # corpus imports nothing from here

    if recs is None:
        recs = json.load(open(config.path(config.INTERIM, "pangaea_treering.json")))
    report: collections.Counter = collections.Counter()
    seen: dict[tuple[str, str], int] = {}
    logs = []
    for r in sorted(recs, key=lambda r: int(r["id"])):
        if DUPLICATES_OF_ITRDB.search(r["author"] or ""):
            report["duplicate of ITRDB (Schweingruber)"] += 1
            continue
        if r["first"] is None:
            report["no dated span"] += 1
            continue
        if r["first"] == 0 and r["last"] == 0:
            report["placeholder span 0-0"] += 1
            continue
        if r["last"] < r["first"]:
            report["last year before first"] += 1
            continue
        if r["floating"]:
            report["floating (relative years)"] += 1
            continue
        if not region.in_scope(r["lat"], r["lon"]):
            report["outside the region or no position"] += 1
            continue
        obj = r["object"] or r["sample"].split("-")[0].split("/")[0]
        key = (obj, r["sample"])
        if key in seen:
            report["same sample deposited twice"] += 1
            continue
        seen[key] = int(r["id"])
        genus, group = corpus.classify(r["species_code"], r["species_name"])
        pressler = r["author"].startswith("Preßler")
        logs.append(corpus.Log(
            key=f"pg-{obj.lower()}/{r['sample']}",
            site=f"pg-{obj.lower()}",
            series_id=r["sample"],
            first_year=r["first"],
            last_year=r["last"],
            n_measured=r["n_rings"] or (r["last"] - r["first"] + 1),
            values=[],
            variant="",
            species_code=r["species_code"],
            species_name=r["species_name"],
            genus=genus,
            group=group,
            site_name=r["place"] or obj,
            location=r["place"],
            lat=r["lat"], lon=r["lon"],
            elevation=str(r["elevation"] or ""),
            investigators=r["author"],
            study_name=(f"{r['project']} - Historical and Postglacial Tree Ring Archive "
                        f"of Hohenheim, object {obj} ({r['kind'] or 'sample'}s)")
                       if r["project"] == "HISTRA" else (r["project"] or ""),
            dois=[],
            url="",
            dating="absolute",
            source="PANGAEA",
            restricted=r["license"] or "access restricted",
            record_doi=r["doi"],
            span_note=PRESSLER_NOTE if pressler else "",
        ))
    if itrdb_logs is not None:
        dup = itrdb_duplicates(logs, itrdb_logs)
        logs = [log for log in logs if log.key not in dup]
        report["same timbers as an ITRDB site"] = len(dup)
    report["plotted"] = len(logs)
    return logs, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parse", action="store_true", help="re-parse saved pages only")
    args = ap.parse_args(argv)
    if not args.parse:
        harvest()
    parse()
    return 0


if __name__ == "__main__":
    sys.exit(main())
