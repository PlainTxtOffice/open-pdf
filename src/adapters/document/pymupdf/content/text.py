"""Adapters for PyMuPDF text extraction and search."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domains.document.models import PdfSearchMatch, PdfTextSpan

if TYPE_CHECKING:
    import pymupdf

_WORD_TUPLE_FIELD_COUNT = 8


def extract_page_text(page: pymupdf.Page) -> str:
    """Return plain text extracted from a page."""
    extracted_text = page.get_text("text")
    return extracted_text if isinstance(extracted_text, str) else ""


def extract_page_words(
    page: pymupdf.Page,
) -> list[tuple[float, float, float, float, str, int, int, int]]:
    """Return extracted word boxes in page coordinates."""
    extracted_words = page.get_text("words")
    if not isinstance(extracted_words, list):
        return []

    normalized_words: list[
        tuple[float, float, float, float, str, int, int, int]
    ] = []
    for word in extracted_words:
        if (
            not isinstance(word, (list, tuple))
            or len(word) < _WORD_TUPLE_FIELD_COUNT
        ):
            continue

        x0, y0, x1, y1, text, block_index, line_index, word_index = word[
            :_WORD_TUPLE_FIELD_COUNT
        ]
        if not isinstance(text, str) or not text:
            continue

        normalized_words.append(
            (
                float(x0),
                float(y0),
                float(x1),
                float(y1),
                text,
                int(block_index),
                int(line_index),
                int(word_index),
            ),
        )

    return normalized_words


def search_document(
    document: pymupdf.Document,
    query: str,
) -> list[PdfSearchMatch]:
    """Return text matches across a document."""
    normalized_query = query.strip()
    if not normalized_query:
        return []

    matches: list[PdfSearchMatch] = []
    for page_index in range(document.page_count):
        page = document.load_page(page_index)
        rectangles = tuple(page.search_for(normalized_query))
        if not rectangles:
            continue

        matches.append(
            PdfSearchMatch(
                page_index=page_index,
                rectangles=rectangles,
            ),
        )

    return matches


def page_text_spans(page: pymupdf.Page, page_index: int) -> list[PdfTextSpan]:
    """Return every styled text span on a page, in reading order."""
    page_dictionary = page.get_text("dict")
    if not isinstance(page_dictionary, dict):
        return []

    spans: list[PdfTextSpan] = []
    for block in page_dictionary.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not isinstance(text, str) or not text.strip():
                    continue

                x0, y0, x1, y1 = span.get("bbox", (0.0, 0.0, 0.0, 0.0))
                origin_x, origin_y = span.get("origin", (x0, y1))
                spans.append(
                    PdfTextSpan(
                        page_index=page_index,
                        span_index=len(spans),
                        text=text,
                        bounds=(float(x0), float(y0), float(x1), float(y1)),
                        origin=(float(origin_x), float(origin_y)),
                        font_name=str(span.get("font", "")),
                        font_size=float(span.get("size", 0.0)),
                        color=int(span.get("color", 0)),
                    ),
                )

    return spans
