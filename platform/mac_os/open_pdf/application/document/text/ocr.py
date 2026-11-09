"""Run OCR and validate results before storing them."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pymupdf

    from open_pdf.adapters.ocr.backend import PdfOcrBackend
    from open_pdf.domains.document.models import PdfOcrPageResult
    from open_pdf.domains.document.pages.text.ocr import OcrResults


def recognize_page(
    backend: PdfOcrBackend | None,
    results: OcrResults,
    document: pymupdf.Document,
    page_index: int,
    *,
    language_codes: tuple[str, ...] = (),
) -> PdfOcrPageResult:
    """Run OCR for one page and store the derived result.

    Raises:
        RuntimeError: No backend is configured, or the backend returned a
            result for a different page.

    """
    if backend is None:
        msg = "OCR backend is not configured."
        raise RuntimeError(msg)

    result = backend.recognize_page(
        document,
        page_index,
        language_codes=language_codes,
    )
    if result.page_index != page_index:
        msg = "OCR backend returned a result for the wrong page."
        raise RuntimeError(msg)

    results.store(result, page_count=document.page_count)
    return result
