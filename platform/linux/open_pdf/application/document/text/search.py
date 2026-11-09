"""Search across native and OCR page text."""

from __future__ import annotations

from typing import TYPE_CHECKING

from open_pdf.adapters.document.pymupdf.content.text import (
    extract_page_words,
    search_page,
)
from open_pdf.adapters.document.pymupdf.lifecycle import load_document_page
from open_pdf.domains.document.models import PdfSearchMatch, Rectangle
from open_pdf.domains.document.pages.text.ocr_search import match_rectangles

if TYPE_CHECKING:
    import pymupdf

    from open_pdf.domains.document.pages.text.ocr import OcrResults


def search_document(
    document: pymupdf.Document,
    ocr: OcrResults,
    query: str,
) -> list[PdfSearchMatch]:
    """Return text matches across the active document.

    Returns:
        The matching pages and highlight rectangles. Returns an empty list
        when `query` is blank or no pages match.

    """
    normalized_query = query.strip()
    if not normalized_query:
        return []

    matches: list[PdfSearchMatch] = []
    for page_index in range(document.page_count):
        page = load_document_page(document, page_index)
        native_words = extract_page_words(page)
        if native_words:
            rectangles = search_page(page, normalized_query)
        else:
            rectangles = _ocr_matches(ocr, page_index, normalized_query)

        if not rectangles:
            continue

        matches.append(
            PdfSearchMatch(
                page_index=page_index,
                rectangles=rectangles,
            ),
        )

    return matches


def _ocr_matches(
    ocr: OcrResults,
    page_index: int,
    query: str,
) -> tuple[Rectangle, ...]:
    """Return OCR-backed match rectangles for one page."""
    ocr_result = ocr.result(page_index)
    if ocr_result is None:
        return ()

    return match_rectangles(ocr_result.words, query)
