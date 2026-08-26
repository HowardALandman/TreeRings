"""The two small static files that change how the whole site behaves.

web/404.html is the more important of the two, and not for its contents.
Cloudflare Pages decides between "serve a real 404" and "single-page
application, answer every path with index.html and a 200" purely on whether a
top-level 404.html exists.  Without it, `/favicon.ico`, `/robots.txt` and every
typo come back 200 with the app page -- which is exactly how a deploy that had
no favicon at all passed its post-deploy check.  Deleting this file re-enables
that silently, so its existence is pinned here and asserted again against the
live site by scripts/verify_deploy.py.
"""

from __future__ import annotations

import os
import re

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


def read(name: str) -> str:
    return open(os.path.join(WEB, name), encoding="utf-8").read()


def test_404_page_exists_at_the_top_level():
    # Must be exactly web/404.html: Pages only looks for it by that name.
    assert os.path.exists(os.path.join(WEB, "404.html"))


def test_404_page_offers_a_way_back():
    # A 404 that is only decorative wastes the one visit it gets.
    html = read("404.html")
    assert 'href="/"' in html


def test_404_page_is_self_contained():
    # It has to render when the thing the visitor asked for is missing, so it
    # must not depend on app.js or fetch any payload.
    html = read("404.html")
    assert "app.js" not in html
    assert "/data/" not in html


def test_404_page_is_not_indexable():
    assert re.search(r'<meta\s+name="robots"\s+content="[^"]*noindex', read("404.html"))


def test_robots_disallows_the_payload_directory():
    txt = read("robots.txt")
    assert re.search(r"(?m)^User-agent:\s*\*\s*$", txt)
    assert re.search(r"(?m)^Disallow:\s*/data/\s*$", txt)


def test_robots_does_not_reference_files_that_do_not_exist():
    # A Sitemap line pointing at a missing file sends every crawler to a 404.
    for m in re.finditer(r"(?mi)^Sitemap:\s*(\S+)", read("robots.txt")):
        name = m.group(1).rsplit("/", 1)[-1]
        assert os.path.exists(os.path.join(WEB, name)), m.group(1)


def test_robots_says_nothing_about_ai_crawlers():
    # Deliberate: the Cloudflare zone allows crawlers, and this file must not
    # quietly contradict it.  If that policy changes, change both together --
    # this test is the reminder, so update it rather than deleting it.
    txt = read("robots.txt")
    directives = "\n".join(
        line for line in txt.splitlines() if not line.lstrip().startswith("#")
    )
    for bot in ("GPTBot", "CCBot", "Google-Extended", "ClaudeBot", "anthropic-ai"):
        assert bot.lower() not in directives.lower(), bot
