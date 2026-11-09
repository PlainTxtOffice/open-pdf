"""Tests for single-span text replacement."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from open_pdf.application.document.session import PdfDocument


def create_text_pdf(path: Path) -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 120), "alpha beta gamma", fontname="helv", fontsize=14)
    document.save(path)
    document.close()


def test_text_spans_report_their_text_font_and_box(tmp_path: Path) -> None:
    pdf_path = tmp_path / "spans.pdf"
    create_text_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    spans = service.text_spans(page_index=0)

    assert len(spans) == 1
    span = spans[0]
    assert span.text == "alpha beta gamma"
    assert span.font_size == pytest.approx(14.0, abs=0.1)
    assert span.font_name
    assert span.bounds[0] == pytest.approx(72.0, abs=1.0)


def test_replacing_a_span_swaps_its_text_in_the_document(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "replace.pdf"
    create_text_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    span = service.text_spans(page_index=0)[0]

    changed = service.replace_text_span(span=span, text="alpha DELTA gamma")

    assert changed is True
    assert "alpha DELTA gamma" in service.page_text(0)
    assert "alpha beta gamma" not in service.page_text(0)


def test_replacing_a_span_with_its_own_text_changes_nothing(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "noop.pdf"
    create_text_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    span = service.text_spans(page_index=0)[0]

    changed = service.replace_text_span(span=span, text=span.text)

    assert changed is False
    assert service.is_dirty() is False


def test_longer_replacement_shrinks_to_stay_on_one_line(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "shrink.pdf"
    create_text_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    span = service.text_spans(page_index=0)[0]
    original_width = span.bounds[2] - span.bounds[0]

    service.replace_text_span(
        span=span,
        text="alpha beta gamma delta epsilon zeta eta theta",
    )

    spans = service.text_spans(page_index=0)
    assert len(spans) == 1, "replacement must not wrap onto a second line"
    assert spans[0].font_size < span.font_size
    assert spans[0].bounds[2] - spans[0].bounds[0] <= original_width + 1.0


def create_two_line_pdf(path: Path) -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 120), "first line here", fontname="helv", fontsize=12)
    page.insert_text((72, 200), "second line here", fontname="helv", fontsize=12)
    document.save(path)
    document.close()


def test_span_lookup_picks_the_span_the_selection_covers(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "pick.pdf"
    create_two_line_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    span = service.span_for_rectangles(
        page_index=0,
        rectangles=[(72.0, 190.0, 200.0, 205.0)],
    )

    assert span is not None
    assert span.text == "second line here"


def test_span_lookup_returns_none_when_the_selection_misses_text(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "miss.pdf"
    create_two_line_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    span = service.span_for_rectangles(
        page_index=0,
        rectangles=[(400.0, 600.0, 500.0, 650.0)],
    )

    assert span is None
