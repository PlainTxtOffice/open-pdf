"""PyMuPDF adapter operations for background search and OCR."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pymupdf

from open_pdf.adapters.document.pymupdf.content.text import search_document

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from open_pdf.adapters.ocr.backend import PdfOcrBackend
    from open_pdf.domains.document.models import (
        PdfOcrPageResult,
        PdfSearchMatch,
    )


def search_pdf_file(path: Path, query: str) -> list[PdfSearchMatch]:
    """Search one PDF file and close its temporary document handle."""
    document = pymupdf.open(path)
    try:
        return search_document(document, query)
    finally:
        document.close()


def recognize_pdf_pages(
    path: Path,
    *,
    page_indexes: Sequence[int],
    backend: PdfOcrBackend,
    language_codes: tuple[str, ...],
    page_completed: Callable[[int, PdfOcrPageResult], None],
) -> None:
    """Recognize selected PDF pages and report each completed result."""
    document = pymupdf.open(path)
    try:
        for completed_pages, page_index in enumerate(page_indexes, start=1):
            result = backend.recognize_page(
                document,
                page_index,
                language_codes=language_codes,
            )
            page_completed(completed_pages, result)
    finally:
        document.close()
