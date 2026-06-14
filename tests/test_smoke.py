import os
from pathlib import Path

import pytest

from md_to_github_pdf.core import html_to_pdf, wrap_html


@pytest.mark.skipif(not os.environ.get("PDF_SMOKE"), reason="set PDF_SMOKE=1 (needs Chromium)")
def test_html_to_pdf_smoke(tmp_path: Path):
    html = tmp_path / "in.html"
    html.write_text(wrap_html("<h1>smoke</h1><p>hello</p>", title="smoke"), encoding="utf-8")
    pdf = tmp_path / "out.pdf"
    html_to_pdf(html, pdf, wait_ms=15000)
    data = pdf.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 1000
