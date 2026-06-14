import base64

import pytest

from md_to_github_pdf.core import read_source, resolve_image_srcs, wrap_html


def test_wrap_html_light():
    html = wrap_html("<p>hi</p>", title="t", theme="light")
    assert '<article class="markdown-body">' in html
    assert "<p>hi</p>" in html
    assert "github-markdown-light.css" in html


def test_wrap_html_dark():
    html = wrap_html("<p>hi</p>", theme="dark")
    assert "github-markdown-dark.css" in html


def test_wrap_html_escapes_title():
    html = wrap_html("<p>hi</p>", title="<script>x</script>")
    assert "&lt;script&gt;" in html
    assert "<script>x</script>" not in html.split("<body>")[0]


def test_wrap_html_rejects_bad_theme():
    with pytest.raises(ValueError):
        wrap_html("<p>hi</p>", theme="neon")


def test_wrap_html_emoji_toggle():
    assert "twemoji" in wrap_html("", emoji=True)
    assert "twemoji" not in wrap_html("", emoji=False)


def test_wrap_html_twemoji_base_is_v15():
    html = wrap_html("", emoji=True)
    assert "jdecked/twemoji@15" in html


def test_read_source_local(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("# hello")
    text, title, ctx, base_url = read_source(str(f))
    assert text == "# hello"
    assert title == "x"
    assert ctx is None
    assert base_url == f.parent.resolve().as_uri() + "/"


def test_resolve_image_srcs_embeds_local(tmp_path):
    png = b"\x89PNG\r\n\x1a\n"  # 8-byte PNG signature
    (tmp_path / "pic.png").write_bytes(png)
    base_url = tmp_path.resolve().as_uri() + "/"
    out = resolve_image_srcs('<img src="pic.png" alt="a">', base_url)
    expected = base64.b64encode(png).decode("ascii")
    assert f"data:image/png;base64,{expected}" in out
    assert 'src="pic.png"' not in out


def test_resolve_image_srcs_embeds_local_subdir(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "s.png").write_bytes(b"\x89PNG\r\n")
    base_url = tmp_path.resolve().as_uri() + "/"
    out = resolve_image_srcs('<img src="assets/s.png">', base_url)
    assert "data:image/png;base64," in out


def test_resolve_image_srcs_missing_local_left_as_is(tmp_path):
    base_url = tmp_path.resolve().as_uri() + "/"
    html = '<img src="nope.png">'
    # Missing file: keep the resolved file:// path rather than a broken data URI.
    out = resolve_image_srcs(html, base_url)
    assert out.startswith('<img src="file://')
    assert "nope.png" in out


def test_resolve_image_srcs_remote_relative_to_absolute():
    base_url = "https://raw.githubusercontent.com/o/r/main/docs/"
    out = resolve_image_srcs('<img src="img/a.png">', base_url)
    assert 'src="https://raw.githubusercontent.com/o/r/main/docs/img/a.png"' in out


def test_resolve_image_srcs_remote_relative_reescapes_ampersand():
    # GitHub emits the src HTML-escaped; the rewritten absolute src must stay escaped.
    base_url = "https://raw.githubusercontent.com/o/r/main/docs/"
    out = resolve_image_srcs('<img src="img/a.png?w=1&amp;h=2">', base_url)
    assert 'src="https://raw.githubusercontent.com/o/r/main/docs/img/a.png?w=1&amp;h=2"' in out


def test_resolve_image_srcs_skips_absolute():
    base_url = "https://raw.githubusercontent.com/o/r/main/"
    for src in ("https://camo.example/x", "http://e/y.png", "data:image/png;base64,AAA"):
        html = f'<img src="{src}" alt="a">'
        assert resolve_image_srcs(html, base_url) == html


def test_resolve_image_srcs_ignores_data_canonical_src(tmp_path):
    # The camo <img> carries data-canonical-src="..."; only the real src must be touched.
    base_url = tmp_path.resolve().as_uri() + "/"
    html = '<img src="https://camo/x" data-canonical-src="https://orig/y.png">'
    assert resolve_image_srcs(html, base_url) == html


def test_resolve_image_srcs_no_base_url_noop():
    html = '<img src="pic.png">'
    assert resolve_image_srcs(html, None) == html


def test_read_source_blob_url_parses_context_without_fetching():
    # Just check the regex path derives the context; actual fetch would hit network.
    from md_to_github_pdf.core import _BLOB_RE

    m = _BLOB_RE.match("https://github.com/o/r/blob/main/docs/a.md")
    assert m and m.groups() == ("o", "r", "main", "docs/a.md")


def test_render_markdown_rate_limit(monkeypatch):
    import email.message
    from urllib.error import HTTPError

    from md_to_github_pdf import core

    hdrs = email.message.Message()
    hdrs["X-RateLimit-Remaining"] = "0"

    def boom(*args, **kwargs):
        raise HTTPError("https://api.github.com/markdown", 403, "rate limited", hdrs, None)

    monkeypatch.setattr(core, "urlopen", boom)
    with pytest.raises(RuntimeError, match="rate limit"):
        core.render_markdown("x")
