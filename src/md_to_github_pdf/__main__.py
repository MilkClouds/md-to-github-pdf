"""CLI: md-to-github-pdf SOURCE [-o OUT.pdf] ...

SOURCE is a local .md path or an http(s) URL (GitHub blob URLs auto-resolve).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from .core import convert


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="md-to-github-pdf",
        description=(
            "Render a markdown file or URL to PDF matching github.com's "
            "renderer (content only, no repo chrome)."
        ),
    )
    p.add_argument("source", help="Local .md path OR http(s) URL (github.com blob URLs auto-resolve)")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Output .pdf path (default: <basename>.pdf)")
    p.add_argument("--theme", choices=["light", "dark"], default="light")
    p.add_argument("--scale", type=float, default=1.0,
                   help="Font-size multiplier (1.0 = github.com-exact; 0.85 denser).")
    p.add_argument("--no-emoji", dest="emoji", action="store_false",
                   help="Skip Twemoji SVG injection.")
    p.add_argument("--context", default=None,
                   help="Repo 'owner/repo' for #123/@user/relative-image resolution (auto-derived from github.com URLs).")
    p.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"),
                   help="GitHub token (or $GITHUB_TOKEN). Raises rate limit 60→5000 req/hr.")
    p.add_argument("--chrome", default=os.environ.get("CHROME", "google-chrome"))
    p.add_argument("--wait-ms", type=int, default=8000)
    p.add_argument("--keep-html", action="store_true",
                   help="Keep intermediate HTML next to the PDF.")
    args = p.parse_args(argv)

    is_url = bool(re.match(r"^https?://", args.source))
    if not is_url and not Path(args.source).is_file():
        print(f"error: not a file or URL: {args.source}", file=sys.stderr)
        return 2

    if args.output:
        pdf = args.output
    elif is_url:
        stem = Path(args.source.split("?", 1)[0]).stem or "output"
        pdf = Path(f"{stem}.pdf")
    else:
        pdf = Path(args.source).with_suffix(".pdf")
    pdf.parent.mkdir(parents=True, exist_ok=True)

    try:
        out = convert(
            args.source, pdf,
            theme=args.theme, scale=args.scale, emoji=args.emoji,
            context=args.context, token=args.token,
            chrome=args.chrome, wait_ms=args.wait_ms,
            keep_html=args.keep_html,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
