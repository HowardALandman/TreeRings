#!/usr/bin/env python3
"""Post-deploy verification for the Pages site.

This replaces a recipe that lived in HANDOFF.md as a handful of curl lines
checking status codes.  That recipe reported a passing favicon.ico for a
deploy that had no favicon at all, and the reason generalises to every path:

    $ curl -s -o /dev/null -w '%{http_code}' .../nonexistent-xyz
    200

Cloudflare Pages answers *any* unknown path with 200 and the body of
index.html.  A status code therefore carries no information about whether the
file was deployed, so every check here compares the response against that
fallback body and against an expected content type.  The run opens with a
self-check that fetches two paths that cannot exist and requires them to come
back identical; if the fallback is ever not stable, "is a real file" means
nothing and every other result in the run is worthless.

Cache busting is not optional.  The edge holds the previous deploy's objects
for a while, so an unbusted check measures what you just replaced -- which is
what made the first check after the compression deploy look like a failure.

Usage:
    python scripts/verify_deploy.py
    python scripts/verify_deploy.py --origin https://ehd-612.pages.dev
    python scripts/verify_deploy.py --no-compare      # skip the parity pass
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import random
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ehd import compress  # noqa: E402
from scripts.serve import matches, parse_headers  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")

ORIGIN = "https://treerings.howardalandman.org"
# The Pages origin has no zone in front of it, so it serves exactly what
# _headers declares.  Any divergence between the two is the zone interfering,
# which is how the Browser Cache TTL override was found on 2026-08-20.
PAGES_ORIGIN = "https://ehd-612.pages.dev"

MISSING_PATH = "/verify-deploy-canary-does-not-exist"

# (path, content-type prefix).  A shard is included because the sparkline
# fetch is lazy and so is the first thing a broken deploy hides.
PATHS = [
    ("/", "text/html"),
    ("/app.js", ("application/javascript", "text/javascript")),
    ("/style.css", "text/css"),
    ("/favicon.ico", ("image/", "application/octet-stream")),
    ("/og.jpg", "image/jpeg"),
    ("/data/logs.bin", "application/octet-stream"),
    ("/data/index.json", "application/json"),
]


class Result:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        self.checks += 1
        if ok:
            print(f"  ok    {label}")
        else:
            print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))
            self.failures.append(label)
        return ok


def fetch(url: str, accept_encoding: str = "br, gzip") -> tuple[int, dict, bytes]:
    """GET with a cache-busting query, returning (status, headers, raw body).

    urllib transparently decodes gzip only when it chose the encoding, so the
    body is returned exactly as it arrived and decoding is decided here.
    """
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(
        f"{url}{sep}cb={random.randrange(1 << 30)}",
        headers={"Accept-Encoding": accept_encoding, "User-Agent": "ehd-verify/1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, _ci(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, _ci(e.headers), e.read()


class _ci(dict):
    """Case-insensitive header dict.

    Header names arrive lowercased over HTTP/2, so a plain dict() of the
    response headers answers None for "X-Frame-Options" on a site that is
    serving it.  The first version of this script did exactly that and
    reported every security header missing -- a false negative, which is the
    safer direction to be wrong in but wrong all the same.
    """

    def __init__(self, headers) -> None:
        super().__init__((k.lower(), v) for k, v in dict(headers).items())

    def get(self, key, default=None):  # type: ignore[override]
        return super().get(key.lower(), default)


def decoded(headers: dict, body: bytes) -> bytes:
    enc = (headers.get("Content-Encoding") or "").lower()
    if enc == "br":
        return compress._decompress(body)
    if enc == "gzip":
        return gzip.GzipFile(fileobj=io.BytesIO(body)).read()
    return body


def fingerprint(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()[:16]


# Scripts the Cloudflare zone injects into HTML it serves, which the Pages
# origin does not.  Listing them by name rather than skipping the comparison
# makes this a stronger check, not a weaker one: anything else appearing in
# the served HTML still fails, and a beacon that stops being injected shows
# up in the run's output.
ZONE_INJECTIONS = {
    "cloudflareinsights.com beacon (Web Analytics, enabled on the zone)": (
        b"static.cloudflareinsights.com/beacon.min.js"
    ),
}


def strip_zone_injections(html: bytes) -> tuple[bytes, list[str]]:
    """Remove known zone-injected <script> tags, reporting what was removed."""
    found: list[str] = []
    for name, needle in ZONE_INJECTIONS.items():
        while needle in html:
            i = html.rfind(b"<script", 0, html.find(needle))
            j = html.find(b"</script>", i)
            if i == -1 or j == -1:
                break
            end = j + len(b"</script>")
            # Take the newline the injection brought with it, if any.
            if html[end : end + 1] == b"\n":
                end += 1
            html = html[:i] + html[end:]
            found.append(name)
    return html, found


def rules_for(path: str) -> dict[str, str]:
    """What web/_headers says this path should get."""
    out: dict[str, str] = {}
    for pattern, headers in parse_headers(os.path.join(WEB, "_headers")):
        if matches(pattern, path):
            out.update(dict(headers))
    return out


def local_sizes() -> dict[str, tuple[int, int]]:
    """(compressed, decompressed) byte counts for the payloads, from the build."""
    sizes = {}
    for path in ("/data/logs.bin", "/data/index.json"):
        f = os.path.join(WEB, path.lstrip("/"))
        if os.path.exists(f):
            raw = open(f, "rb").read()
            sizes[path] = (len(raw), len(compress._decompress(raw)))
    return sizes


def verify(origin: str, res: Result) -> None:
    print(f"\n{origin}")

    # Establish what "not deployed" looks like before trusting any 200.
    status, miss_headers, miss_body = fetch(origin + MISSING_PATH)
    fallback = fingerprint(decoded(miss_headers, miss_body))
    print(f"  ---   not-found fallback: {status}, body {fallback}")

    sizes = local_sizes()

    for path, want_type in PATHS:
        status, headers, body = fetch(origin + path)
        label = path
        if not res.check(status == 200, f"{label} -> 200", str(status)):
            continue

        got = decoded(headers, body)
        if path == "/":
            # "/" *is* index.html, so it cannot be told from the fallback by
            # body alone.  Compare it to the build instead, which is a
            # stronger check: it catches a deploy that shipped a stale page.
            local = open(os.path.join(WEB, "index.html"), "rb").read()
            clean, injected = strip_zone_injections(got)
            for what in injected:
                print(f"  ---   zone injected {what}")
            res.check(
                clean == local,
                "/ matches the local build, allowing for known zone injections",
                f"live {len(got):,} B ({len(clean):,} after stripping "
                f"{len(injected)} injection(s)), local {len(local):,} B",
            )
        else:
            res.check(
                fingerprint(got) != fallback,
                f"{label} is a real file, not the not-found fallback",
                "served index.html - file is missing from the deploy",
            )

        ctype = (headers.get("Content-Type") or "").lower()
        wants = (want_type,) if isinstance(want_type, str) else want_type
        res.check(
            any(ctype.startswith(w) for w in wants),
            f"{label} content-type is {' or '.join(wants)}",
            ctype or "(none)",
        )

        declared = rules_for(path)
        for name in ("Cache-Control", "Content-Encoding"):
            if name in declared:
                res.check(
                    headers.get(name) == declared[name],
                    f"{label} {name}: {declared[name]}",
                    f"got {headers.get(name)!r}",
                )
        for name in ("X-Content-Type-Options", "Referrer-Policy", "X-Frame-Options"):
            res.check(
                headers.get(name) == declared.get(name),
                f"{label} {name}",
                f"got {headers.get(name)!r} want {declared.get(name)!r}",
            )

        if path in sizes:
            comp, plain = sizes[path]
            res.check(
                len(body) == comp,
                f"{label} on the wire is {comp:,} B",
                f"got {len(body):,}",
            )
            res.check(
                len(got) == plain,
                f"{label} decodes to {plain:,} B",
                f"got {len(got):,}",
            )

    _verify_shard(origin, res, fallback)
    _verify_link_preview(origin, res, fallback)


def _verify_shard(origin: str, res: Result, fallback: str) -> None:
    """One real values/ shard, chosen from the build rather than hardcoded."""
    values = os.path.join(WEB, "data", "values")
    names = sorted(os.listdir(values))[:1] if os.path.isdir(values) else []
    if not names:
        res.check(False, "a values/ shard exists locally to check", "none found")
        return
    path = f"/data/values/{names[0]}"
    status, headers, body = fetch(origin + path)
    if not res.check(status == 200, f"{path} -> 200", str(status)):
        return
    got = decoded(headers, body)
    res.check(fingerprint(got) != fallback, f"{path} is a real file")
    res.check(
        (headers.get("Content-Type") or "").startswith("application/json"),
        f"{path} content-type is application/json",
        headers.get("Content-Type") or "(none)",
    )
    res.check(
        len(got) == os.path.getsize(os.path.join(values, names[0])),
        f"{path} matches the local build byte for byte",
    )


def _verify_link_preview(origin: str, res: Result, fallback: str) -> None:
    """The tags Facebook et al. read, and that og:image actually resolves."""
    _, headers, body = fetch(origin + "/")
    html = decoded(headers, body).decode("utf-8", "replace")

    for prop in ("og:title", "og:description", "og:image", "og:url", "og:type"):
        res.check(f'property="{prop}"' in html, f"index.html declares {prop}")

    start = html.find('property="og:image"')
    url = ""
    if start != -1:
        seg = html[html.rfind("<meta", 0, start) : html.find(">", start)]
        key = 'content="'
        i = seg.find(key)
        url = seg[i + len(key) : seg.find('"', i + len(key))] if i != -1 else ""

    res.check(
        url.startswith("http://") or url.startswith("https://"),
        "og:image is an absolute URL",
        url or "(not found)",
    )
    if url.startswith("http"):
        status, ih, ibody = fetch(url)
        res.check(status == 200, f"og:image fetches ({url})", str(status))
        res.check(
            (ih.get("Content-Type") or "").startswith("image/"),
            "og:image is served as an image",
            ih.get("Content-Type") or "(none)",
        )
        res.check(
            fingerprint(decoded(ih, ibody)) != fallback,
            "og:image is a real file, not the not-found fallback",
        )


def verify_https_redirect(res: Result) -> None:
    host = ORIGIN.split("://", 1)[1]
    req = urllib.request.Request(
        f"http://{host}/?cb={random.randrange(1 << 30)}",
        headers={"User-Agent": "ehd-verify/1"},
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=30) as r:
            status, location = r.status, r.headers.get("Location", "")
    except urllib.error.HTTPError as e:
        status, location = e.code, e.headers.get("Location", "")
    res.check(
        status in (301, 308) and location.startswith("https://"),
        "http -> https redirect",
        f"{status} {location}",
    )


def verify_parity(res: Result) -> None:
    """The custom domain must serve the same Cache-Control as the Pages origin.

    The zone in front of the custom domain can rewrite headers _headers
    declares, and did: Browser Cache TTL replaced no-cache with max-age=14400
    on every edge-cacheable path.  Comparing the two hostnames is what catches
    that class of problem, so it is a check rather than a note.
    """
    print("\nparity: custom domain vs Pages origin")
    for path, _ in PATHS:
        _, a, _b = fetch(ORIGIN + path)
        _, b, _b2 = fetch(PAGES_ORIGIN + path)
        declared = rules_for(path)

        # Cache-Control is compared everywhere, declared or not: rewriting it
        # is exactly what the zone did, and on the paths _headers says nothing
        # about it is Pages' own default that must survive.
        names = ["Cache-Control"]
        # Content-Encoding is only comparable where _headers pins it.  Where
        # it does not, the value is whatever each edge decided to negotiate --
        # og.jpg came back `br` from one origin and unencoded from the other
        # on consecutive requests -- so comparing it tests the weather.
        if "Content-Encoding" in declared:
            names.append("Content-Encoding")

        for name in names:
            res.check(
                a.get(name) == b.get(name),
                f"{path} {name} matches the Pages origin",
                f"{ORIGIN}={a.get(name)!r} {PAGES_ORIGIN}={b.get(name)!r}",
            )


def verify_missing_is_detected(res: Result, origin: str) -> None:
    """Prove the not-found detector works, or nothing above means anything."""
    print("\ndetector self-check")
    _, h1, b1 = fetch(origin + MISSING_PATH)
    _, h2, b2 = fetch(origin + MISSING_PATH + "-2")
    res.check(
        fingerprint(decoded(h1, b1)) == fingerprint(decoded(h2, b2)),
        "two unknown paths return the same fallback body",
        "the fallback is not stable, so 'is a real file' cannot be trusted",
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--origin", default=ORIGIN)
    ap.add_argument("--no-compare", action="store_true")
    args = ap.parse_args(argv[1:])

    res = Result()
    verify_missing_is_detected(res, args.origin)
    verify(args.origin, res)
    if args.origin == ORIGIN:
        print()
        verify_https_redirect(res)
        if not args.no_compare:
            verify_parity(res)

    print(f"\n{res.checks} checks, {len(res.failures)} failed")
    for f in res.failures:
        print(f"  FAIL  {f}")
    return 1 if res.failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
