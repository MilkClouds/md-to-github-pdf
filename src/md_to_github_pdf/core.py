"""md → github.com-styled PDF.

Pipeline: source (local path or URL) → GitHub /markdown API (GFM) →
github-markdown-css + highlight.js + Twemoji → headless Chrome --print-to-pdf.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

GITHUB_API = "https://api.github.com/markdown"

CSS_BASE = "https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown-{theme}.css"
CSS_HLJS = "https://cdn.jsdelivr.net/npm/highlight.js@11/styles/{hljs_theme}.min.css"
JS_HLJS = "https://cdn.jsdelivr.net/npm/highlight.js@11/lib/common.min.js"
JS_TWEMOJI = "https://cdn.jsdelivr.net/npm/@twemoji/api@15/dist/twemoji.min.js"
TWEMOJI_BASE = "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/"

_BLOB_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$")
_RAW_RE = re.compile(r"^https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/")


def read_source(src: str) -> tuple[str, str, str | None]:
    """Resolve src (local path or URL) to (markdown_text, title, auto_context).

    For a github.com blob URL, rewrites to raw.githubusercontent.com and
    derives `owner/repo` as auto_context. For a raw URL, derives auto_context.
    For a local path, title is the filename stem.
    """
    if re.match(r"^https?://", src):
        url = src
        auto_ctx: str | None = None
        m = _BLOB_RE.match(url)
        if m:
            owner, repo, branch, path = m.groups()
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
            auto_ctx = f"{owner}/{repo}"
        else:
            m2 = _RAW_RE.match(url)
            if m2:
                auto_ctx = f"{m2.group(1)}/{m2.group(2)}"
        with urlopen(url, timeout=30) as resp:
            text = resp.read().decode("utf-8")
        title = Path(url.split("?", 1)[0]).stem
        return text, title, auto_ctx

    path = Path(src)
    return path.read_text(encoding="utf-8"), path.stem, None


def render_markdown(
    md_text: str,
    *,
    context: str | None = None,
    token: str | None = None,
    timeout: float = 30.0,
) -> str:
    """POST to GitHub's /markdown API. Returns an HTML fragment."""
    payload: dict[str, str] = {"text": md_text, "mode": "gfm"}
    if context:
        payload["context"] = context
    req = Request(
        GITHUB_API,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "md-to-github-pdf",
        },
        method="POST",
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def wrap_html(
    body_html: str,
    *,
    title: str = "",
    theme: str = "light",
    scale: float = 1.0,
    emoji: bool = True,
) -> str:
    """Wrap an HTML fragment with github-markdown-css, highlight.js, Twemoji."""
    if theme not in {"light", "dark"}:
        raise ValueError(f"theme must be 'light' or 'dark', got {theme!r}")
    if scale <= 0:
        raise ValueError(f"scale must be > 0, got {scale}")
    base_css = CSS_BASE.format(theme=theme)
    hljs_css = CSS_HLJS.format(hljs_theme="github-dark" if theme == "dark" else "github")
    bg = "#0d1117" if theme == "dark" else "#ffffff"
    color_scheme = "dark" if theme == "dark" else "light"

    twemoji_tag = f'<script src="{JS_TWEMOJI}" defer></script>' if emoji else ""
    twemoji_call = (
        f"if (window.twemoji) {{ window.twemoji.parse(document.body, "
        f'{{ folder: "svg", ext: ".svg", base: "{TWEMOJI_BASE}" }}); }}'
        if emoji
        else ""
    )
    return f"""<!doctype html>
<html lang="en" data-color-mode="{color_scheme}" data-{color_scheme}-theme="{color_scheme}">
<head>
<meta charset="utf-8">
<title>{_escape(title)}</title>
<link rel="stylesheet" href="{base_css}">
<link rel="stylesheet" href="{hljs_css}">
<script src="{JS_HLJS}" defer></script>
{twemoji_tag}
<style>
  @page {{ size: A4; margin: 18mm 14mm; }}
  html, body {{ background: {bg}; margin: 0; padding: 0; color-scheme: {color_scheme}; }}
  .markdown-body {{
    box-sizing: border-box; min-width: 200px; max-width: 980px;
    margin: 0 auto; padding: 28px 36px;
    font-size: {16 * scale:.2f}px;
  }}
  .markdown-body img.emoji {{
    height: 1em; width: 1em; margin: 0 0.05em 0 0.1em; vertical-align: -0.1em;
  }}
  @media print {{
    .markdown-body {{ padding: 0; max-width: 100%; }}
    .markdown-body pre, .markdown-body code {{
      white-space: pre-wrap; word-wrap: break-word;
    }}
    .markdown-body img, .markdown-body table, .markdown-body pre {{
      page-break-inside: avoid;
    }}
  }}
</style>
</head>
<body>
<article class="markdown-body">
{body_html}
</article>
<script>window.addEventListener('load', () => {{
  if (window.hljs) {{
    document.querySelectorAll('pre code').forEach(el => window.hljs.highlightElement(el));
  }}
  {twemoji_call}
}});</script>
</body>
</html>
"""


def html_to_pdf(
    html_path: Path,
    pdf_path: Path,
    *,
    chrome: str = "google-chrome",
    wait_ms: int = 8000,
) -> None:
    """Render HTML at html_path to pdf_path via headless Chromium."""
    if shutil.which(chrome) is None and not Path(chrome).exists():
        raise FileNotFoundError(
            f"chrome executable not found: {chrome}. "
            "Install google-chrome or set --chrome/$CHROME."
        )
    cmd = [
        chrome,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--hide-scrollbars",
        # Chrome <=120 used --print-to-pdf-no-header; Chrome 121+ renamed it.
        "--no-pdf-header-footer",
        "--print-to-pdf-no-header",
        f"--virtual-time-budget={wait_ms}",
        f"--print-to-pdf={pdf_path.resolve()}",
        f"file://{html_path.resolve()}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not pdf_path.exists():
        raise RuntimeError(
            f"chrome print-to-pdf failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def convert(
    source: str,
    pdf_path: Path,
    *,
    theme: str = "light",
    scale: float = 1.0,
    emoji: bool = True,
    context: str | None = None,
    token: str | None = None,
    chrome: str = "google-chrome",
    wait_ms: int = 8000,
    keep_html: bool = False,
) -> Path:
    """End-to-end. source is a local path or a URL. Returns resolved PDF path."""
    md_text, title, auto_ctx = read_source(source)
    effective_context = context or auto_ctx
    body_html = render_markdown(md_text, context=effective_context, token=token)
    full_html = wrap_html(
        body_html, title=title, theme=theme, scale=scale, emoji=emoji
    )

    if keep_html:
        html_path = pdf_path.with_suffix(".html")
        html_path.write_text(full_html, encoding="utf-8")
        html_to_pdf(html_path, pdf_path, chrome=chrome, wait_ms=wait_ms)
    else:
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".html", delete=False, encoding="utf-8"
        )
        try:
            tmp.write(full_html)
            tmp.close()
            html_to_pdf(Path(tmp.name), pdf_path, chrome=chrome, wait_ms=wait_ms)
        finally:
            Path(tmp.name).unlink(missing_ok=True)
    return pdf_path.resolve()


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
