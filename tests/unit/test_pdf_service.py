"""Tests for PDFService"""

import pytest

try:
    from backend.common.pdf_service import PDFService

    PDF_AVAILABLE = True
except Exception:
    PDF_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not PDF_AVAILABLE,
    reason="weasyprint system libs (pango/cairo) not available on this machine",
)


def test_render_pdf_returns_bytes():
    svc = PDFService()
    html = "<html><body><p>Hello</p></body></html>"
    pdf = svc.render_pdf(html)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")


def test_render_pdf_empty_html():
    svc = PDFService()
    pdf = svc.render_pdf("")
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")


def test_render_pdf_chinese_text():
    svc = PDFService()
    html = "<html><body><p>中文测试</p></body></html>"
    pdf = svc.render_pdf(html)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 100


def test_render_pdf_invalid_html():
    svc = PDFService()
    pdf = svc.render_pdf("<html><body><p>Unclosed")
    assert pdf.startswith(b"%PDF")
