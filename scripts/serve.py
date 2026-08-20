#!/usr/bin/env python3
"""Serve web/ locally the way Cloudflare Pages serves it.

`python -m http.server` is no longer enough: ehd.emit writes logs.bin and
index.json brotli-compressed under their plain names, and in production
web/_headers is what tells the browser so.  A plain file server omits that
header, the browser hands app.js a compressed buffer, and the viewer draws
nothing -- which looks like a bug in the viewer rather than in the server.

This reads web/_headers and applies it, so local and deployed behaviour differ
only in what Cloudflare adds on top.  It deliberately does not implement
content negotiation, because production does not either.

Usage:
    python scripts/serve.py [port]      # default 8777
"""

from __future__ import annotations

import functools
import http.server
import os
import sys

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


def parse_headers(path: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """Parse a Cloudflare Pages _headers file into (pattern, headers) rules.

    Only the subset this project uses is supported: leading/trailing `*` globs
    on the path, no placeholders, no absolute URLs, no `!` detach lines.  Any
    line that is not one of those raises, so an unsupported rule shows up here
    instead of quietly not being served.
    """
    rules: list[tuple[str, list[tuple[str, str]]]] = []
    for lineno, raw in enumerate(open(path), 1):
        line = raw.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0].isspace():
            if not rules:
                raise ValueError(f"{path}:{lineno}: header before any URL pattern")
            name, sep, value = line.strip().partition(":")
            if not sep or name.startswith("!"):
                raise ValueError(f"{path}:{lineno}: unsupported header line {line!r}")
            rules[-1][1].append((name.strip(), value.strip()))
        else:
            if not line.startswith("/") or line.count("*") > 1:
                raise ValueError(f"{path}:{lineno}: unsupported URL pattern {line!r}")
            rules.append((line.strip(), []))
    return rules


def matches(pattern: str, path: str) -> bool:
    head, sep, tail = pattern.partition("*")
    if not sep:
        return path == pattern
    return path.startswith(head) and path.endswith(tail)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, rules, **kwargs):
        self.rules = rules
        super().__init__(*args, directory=WEB, **kwargs)

    def send_head(self):
        # Pages parses these and does not serve them; neither should we, or a
        # config file would look reachable locally and 404 in production.
        if self.path.split("?", 1)[0] in ("/_headers", "/_redirects"):
            self.send_error(404, "not served (parsed by Pages)")
            return None
        return super().send_head()

    def end_headers(self):
        path = self.path.split("?", 1)[0]
        if path.endswith("/"):
            path += "index.html"
        for pattern, headers in self.rules:
            if matches(pattern, path):
                for name, value in headers:
                    self.send_header(name, value)
        super().end_headers()

    def log_message(self, fmt, *args):  # quieter: one line per request
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


def main(argv: list[str]) -> int:
    port = int(argv[1]) if len(argv) > 1 else 8777
    rules = parse_headers(os.path.join(WEB, "_headers"))
    print(f"serving {WEB} on http://localhost:{port}/")
    for pattern, headers in rules:
        for name, value in headers:
            print(f"  {pattern:<18} {name}: {value}")
    handler = functools.partial(Handler, rules=rules)
    http.server.ThreadingHTTPServer(("", port), handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
