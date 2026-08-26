"""The link-preview tags and the files they point at must stay in step.

Facebook, LinkedIn, Slack and Discord read the served HTML and never run
app.js, so the visualisation -- which exists only as pixels app.js draws into
a <canvas> -- is invisible to them.  Everything a shared link shows therefore
comes from static tags in index.html plus a static image file, and the two
halves fail independently: a tag pointing at a file that isn't deployed gives
the same blank card as no tag at all.

These are offline checks against the build.  scripts/verify_deploy.py runs the
same reasoning against the live site, where it can also catch the file being
missing from the deploy.
"""

from __future__ import annotations

import os
import re
import struct

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
HTML = open(os.path.join(WEB, "index.html")).read()

ORIGIN = "https://treerings.howardalandman.org"


def meta(prop: str) -> str | None:
    m = re.search(
        rf'<meta\s+property="{re.escape(prop)}"\s+content="([^"]*)"', HTML
    )
    return m.group(1) if m else None


def test_required_og_properties_are_present():
    # og:image alone is not enough -- without a title and type Facebook will
    # render a card, but a degraded one.
    for prop in ("og:type", "og:url", "og:title", "og:description", "og:image"):
        assert meta(prop), prop


def test_og_image_is_absolute():
    # The single most common cause of a blank card: crawlers do not resolve a
    # relative og:image against the page URL.
    url = meta("og:image")
    assert url.startswith("https://"), url
    assert url.startswith(ORIGIN), url


def test_og_image_file_exists_and_is_the_declared_size():
    url = meta("og:image")
    path = os.path.join(WEB, url[len(ORIGIN) :].lstrip("/"))
    assert os.path.exists(path), path

    width, height = jpeg_size(open(path, "rb").read())
    assert (width, height) == (1200, 630), (width, height)
    # The declared dimensions are what let the large card render on the first
    # scrape; if they disagree with the file, the card lays out wrong.
    assert meta("og:image:width") == str(width)
    assert meta("og:image:height") == str(height)


def test_og_image_is_within_facebooks_size_limit():
    url = meta("og:image")
    path = os.path.join(WEB, url[len(ORIGIN) :].lstrip("/"))
    assert os.path.getsize(path) < 8 * 1024 * 1024


def test_og_url_matches_the_site():
    assert meta("og:url").rstrip("/") == ORIGIN


def test_favicons_exist_and_are_linked():
    # /favicon.ico is requested by browsers whether or not it is linked, and
    # Pages answers 200 with index.html when it is absent -- which is how the
    # missing favicon survived a post-deploy check for two days.
    for name in ("favicon.ico", "favicon.svg"):
        assert os.path.exists(os.path.join(WEB, name)), name
        assert f'href="/{name}"' in HTML, name


def test_description_is_present_for_search_results():
    assert re.search(r'<meta\s+name="description"\s+content="[^"]{40,}"', HTML)


def jpeg_size(data: bytes) -> tuple[int, int]:
    """Width and height from a JPEG's first SOF marker.

    Written out rather than imported because the venv has no image library --
    see scripts/make_favicon.py for the same reasoning.
    """
    i = 2  # skip SOI
    while i < len(data):
        assert data[i] == 0xFF, f"not a marker at {i}"
        marker, length = data[i + 1], struct.unpack(">H", data[i + 2 : i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return width, height
        i += 2 + length
    raise AssertionError("no SOF marker found")
