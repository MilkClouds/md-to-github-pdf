import pytest

from md_to_github_pdf.core import read_source, wrap_html


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


def test_read_source_local(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("# hello")
    text, title, ctx = read_source(str(f))
    assert text == "# hello"
    assert title == "x"
    assert ctx is None


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
