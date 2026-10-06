"""Derived OCR output for the active document."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pymupdf

    from src.domains.document.models import PdfOcrBackend, PdfOcrPageResult


class OcrResults:
    """Own the OCR backend and the derived per-page results."""

    def __init__(self, *, backend: PdfOcrBackend | None = None) -> None:
        """Initialize with no stored results."""
        self._backend = backend
        self._results_by_page: dict[int, PdfOcrPageResult] = {}

    def has_backend(self) -> bool:
        """Return whether an OCR backend is configured."""
        return self._backend is not None

    def result(self, page_index: int) -> PdfOcrPageResult | None:
        """Return the stored OCR output for one page, if present."""
        return self._results_by_page.get(page_index)

    def has_result(self, page_index: int) -> bool:
        """Return whether OCR output exists for one page."""
        return self.result(page_index) is not None

    def has_any(self) -> bool:
        """Return whether any OCR output is stored."""
        return bool(self._results_by_page)

    def run(
        self,
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
        if self._backend is None:
            msg = "OCR backend is not configured."
            raise RuntimeError(msg)

        result = self._backend.recognize_page(
            document,
            page_index,
            language_codes=language_codes,
        )
        if result.page_index != page_index:
            msg = "OCR backend returned a result for the wrong page."
            raise RuntimeError(msg)

        self.store(result, page_count=document.page_count)
        return result

    def store(self, result: PdfOcrPageResult, *, page_count: int) -> None:
        """Store one derived OCR page result.

        Raises:
            ValueError: The result's page index is outside the document.

        """
        if not 0 <= result.page_index < page_count:
            msg = f"Page index {result.page_index} is out of range."
            raise ValueError(msg)

        self._results_by_page[result.page_index] = result

    def replace(
        self,
        results: Sequence[PdfOcrPageResult],
        *,
        page_count: int,
    ) -> None:
        """Replace all stored OCR output."""
        self.clear()
        for result in results:
            self.store(result, page_count=page_count)

    def all(self) -> tuple[PdfOcrPageResult, ...]:
        """Return all stored results ordered by page index."""
        return tuple(
            self._results_by_page[page_index]
            for page_index in sorted(self._results_by_page)
        )

    def clear(self) -> None:
        """Drop all derived OCR output."""
        self._results_by_page.clear()
