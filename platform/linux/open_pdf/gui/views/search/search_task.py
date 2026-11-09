"""Background full-document search tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRunnable, Signal

from open_pdf.adapters.document.errors import PDF_IO_ERRORS
from open_pdf.adapters.document.pymupdf.processing import search_pdf_file

if TYPE_CHECKING:
    from pathlib import Path


class SearchTaskSignals(QObject):
    """Signals emitted by one background search task."""

    completed = Signal(int, str, object)
    failed = Signal(int, str, str)


class SearchTask(QRunnable):
    """Search a PDF for a query in a worker thread."""

    def __init__(
        self,
        *,
        source_path: Path,
        query: str,
        generation: int,
    ) -> None:
        """Store the inputs for one background search job."""
        super().__init__()
        self._source_path = source_path
        self._query = query
        self._generation = generation
        self.signals = SearchTaskSignals()

    def run(self) -> None:
        """Perform the search and emit the result."""
        try:
            matches = search_pdf_file(self._source_path, self._query)
        except PDF_IO_ERRORS as error:
            self.signals.failed.emit(
                self._generation,
                self._query,
                str(error),
            )
            return

        self.signals.completed.emit(
            self._generation,
            self._query,
            matches,
        )
