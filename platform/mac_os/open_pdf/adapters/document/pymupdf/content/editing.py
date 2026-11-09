"""PyMuPDF editing operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pymupdf

if TYPE_CHECKING:
    from collections.abc import Sequence

    from open_pdf.domains.document.models import PdfTextSpan


_FALLBACK_FONT = "helv"


_MIN_REPLACEMENT_FONT_SIZE = 4.0


def _replacement_font_name(font_name: str) -> str:
    """Return a font usable for arbitrary replacement characters."""
    base_14 = {"helv", "tiro", "cour", "times", "symb", "zadb"}
    normalized = font_name.rsplit("+", maxsplit=1)[-1].casefold()
    for candidate in base_14:
        if normalized.startswith(candidate):
            return candidate
    return _FALLBACK_FONT


def insert_blank_document_page(
    document: pymupdf.Document,
    *,
    page_index: int,
    size: tuple[float, float],
) -> None:
    """Insert an empty page of `size` at `page_index`."""
    width, height = size
    document.new_page(pno=page_index, width=width, height=height)


def delete_document_page(
    document: pymupdf.Document,
    page_index: int,
) -> None:
    """Delete one page from the active document."""
    document.delete_page(page_index)


def move_document_page(
    document: pymupdf.Document,
    page_index: int,
    destination_index: int,
) -> None:
    """Move one page to another zero-based page position."""
    insert_index = destination_index
    if page_index < destination_index:
        insert_index = (
            -1
            if destination_index == document.page_count - 1
            else destination_index + 1
        )
    document.move_page(page_index, insert_index)


def redact_page_rectangles(
    document: pymupdf.Document,
    page_index: int,
    rectangles: Sequence[tuple[float, float, float, float]],
) -> bool:
    """Redact page content inside the supplied PDF-space rectangles."""
    page = document.load_page(page_index)
    added_redaction = False
    for x0, y0, x1, y1 in rectangles:
        rect = pymupdf.Rect(
            min(x0, x1),
            min(y0, y1),
            max(x0, x1),
            max(y0, y1),
        )
        if rect.is_empty:
            continue

        page.add_redact_annot(rect, fill=(1, 1, 1))
        added_redaction = True

    if not added_redaction:
        return False

    page.apply_redactions()
    return True


def replace_text_span(
    document: pymupdf.Document,
    *,
    span: PdfTextSpan,
    text: str,
) -> bool:
    """Erase the text inside `bounds` and draw `text` on the same baseline.

    - Stays on one line: PDF has no reflow, so wrapping would collide with
      the line beneath. Longer text shrinks to fit the original width,
      down to a floor, and is allowed to run on if it still will not fit.

    Returns:
        True when the page was modified.

    """
    page = document.load_page(span.page_index)
    span_rect = pymupdf.Rect(*span.bounds)
    if span_rect.is_empty:
        return False

    page.add_redact_annot(span_rect)
    page.apply_redactions()

    if not text:
        return True

    replacement_font = _replacement_font_name(span.font_name)
    rgb = (
        ((span.color >> 16) & 0xFF) / 255.0,
        ((span.color >> 8) & 0xFF) / 255.0,
        (span.color & 0xFF) / 255.0,
    )
    available_width = span_rect.width
    size = span.font_size
    while size > _MIN_REPLACEMENT_FONT_SIZE:
        width = pymupdf.get_text_length(
            text,
            fontname=replacement_font,
            fontsize=size,
        )
        if width <= available_width:
            break
        size -= 0.5

    page.insert_text(
        pymupdf.Point(span.origin),
        text,
        fontname=replacement_font,
        fontsize=size,
        color=rgb,
    )
    return True


def rotate_page_clockwise(document: pymupdf.Document, page_index: int) -> None:
    """Rotate one page by ninety degrees."""
    page = document.load_page(page_index)
    page.set_rotation((page.rotation + 90) % 360)
