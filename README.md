# md-to-github-pdf

Render a Markdown file (or a github.com URL) to PDF **matching github.com's renderer** — content only, no repo chrome.

Every other tool either uses a local Markdown parser (not pixel-identical to github.com) or a dead wkhtmltopdf backend. This one delegates rendering to GitHub's own `/markdown` API and prints with modern headless Chrome.

## Install

```bash
uv tool install md-to-github-pdf
```

Chromium is auto-downloaded on first use (one-time, ~170MB) — no system Chrome required.

## Use

```bash
md-to-github-pdf README.md                                        # local
md-to-github-pdf https://github.com/owner/repo/blob/main/FILE.md  # remote (github.com blob URL)
md-to-github-pdf https://raw.githubusercontent.com/o/r/main/F.md  # remote (raw URL)

md-to-github-pdf file.md --theme dark
md-to-github-pdf file.md --scale 0.85        # denser typography
md-to-github-pdf file.md -o out.pdf
GITHUB_TOKEN=ghp_... md-to-github-pdf file.md  # 60→5000 req/hr
```

Output path defaults to `<basename>.pdf`. GitHub URLs auto-resolve `owner/repo` context so relative images and `#123` references work.

## How

`md` → GitHub `/markdown` API (`mode=gfm`) → `github-markdown-css` + `highlight.js` + Twemoji SVGs → Playwright's bundled Chromium `page.pdf()`.

GFM extensions — `> [!NOTE]` alerts, `- [x]` task lists, tables, footnotes, emoji shortcodes — all handled by the API, so the output is byte-identical to what github.com renders.

## Limits

- Network required (GitHub API + jsDelivr CDN)
- Mermaid blocks not rendered (github.com page-level feature, outside `/markdown` API)
- Unauthenticated rate limit: 60 req/hr (use `GITHUB_TOKEN` for 5000)

## License

MIT
