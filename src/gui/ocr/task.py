"""Background OCR tasks for PDF pages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRunnable, Signal

from src.adapters.document.pymupdf.processing import recognize_pdf_pages

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from src.domains.document.models import PdfOcrBackend


class OcrTaskSignals(QObject):
    """Signals emitted by one OCR background task."""

    page_completed = Signal(int, int, int, int, object)
    failed = Signal(int, str)
    completed = Signal(int, int)


class OcrTask(QRunnable):
    """Recognize text for one or more pages in a worker thread."""

    def __init__(
        self,
        *,
        source_path: Path,
        page_indexes: Sequence[int],
        generation: int,
        ocr_backend: PdfOcrBackend,
        language_codes: tuple[str, ...] = (),
    ) -> None:
        """Store the inputs for one OCR worker job."""
        super().__init__()
        self._source_path = source_path
        self._page_indexes = tuple(page_indexes)
        self._generation = generation
        self._ocr_backend = ocr_backend
        self._language_codes = language_codes
        self.signals = OcrTaskSignals()

    def run(self) -> None:
        """Perform OCR and emit per-page progress plus the final result."""
        total_pages = len(self._page_indexes)
        try:
            recognize_pdf_pages(
                self._source_path,
                page_indexes=self._page_indexes,
                backend=self._ocr_backend,
                language_codes=self._language_codes,
                page_completed=lambda completed_pages, result: (
                    self.signals.page_completed.emit(
                        self._generation,
                        result.page_index,
                        completed_pages,
                        total_pages,
                        result,
                    )
                ),
            )
        except Exception as error:  # noqa: BLE001
            self.signals.failed.emit(self._generation, str(error))
            return

        self.signals.completed.emit(
            self._generation,
            len(self._page_indexes),
        )
