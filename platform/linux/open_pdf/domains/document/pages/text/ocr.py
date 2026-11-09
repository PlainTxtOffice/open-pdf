"""Derived OCR output for the active document."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from open_pdf.domains.document.models import PdfOcrPageResult


class OcrResults:
    """Own the derived per-page OCR results."""

    def __init__(self) -> None:
        """Initialize with no stored results."""
        self._results_by_page: dict[int, PdfOcrPageResult] = {}

    def result(self, page_index: int) -> PdfOcrPageResult | None:
        """Return the stored OCR output for one page, if present."""
        return self._results_by_page.get(page_index)

    def has_result(self, page_index: int) -> bool:
        """Return whether OCR output exists for one page."""
        return self.result(page_index) is not None

    def has_any(self) -> bool:
        """Return whether any OCR output is stored."""
        return bool(self._results_by_page)

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
