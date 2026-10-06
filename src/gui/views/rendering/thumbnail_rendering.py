"""Background thumbnail rendering tasks for the PySide6 PDF view."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRunnable, Signal

from src.adapters.document.pymupdf.document import render_thumbnail
from src.adapters.document.pymupdf.qt import qimage_from_pymupdf
from src.domains.document.errors import PDF_IO_ERRORS
from src.gui.views.rendering.render_handle_cache import RENDER_HANDLE_CACHE

if TYPE_CHECKING:
    from pathlib import Path

    from PySide6.QtGui import QImage


class ThumbnailRenderSignals(QObject):
    """Signals emitted by one background thumbnail render task."""

    rendered = Signal(int, int, object)
    failed = Signal(int, int, str)


class ThumbnailRenderTask(QRunnable):
    """Render one PDF page thumbnail into a detached Qt image."""

    def __init__(
        self,
        *,
        source_path: Path,
        render_revision: int,
        page_index: int,
        max_dimension: int,
        generation: int,
    ) -> None:
        """Store the inputs for one background thumbnail render job."""
        super().__init__()
        self._source_path = source_path
        self._render_revision = render_revision
        self._page_index = page_index
        self._max_dimension = max_dimension
        self._generation = generation
        self.signals = ThumbnailRenderSignals()

    def run(self) -> None:
        """Render the configured thumbnail and emit the result."""
        try:
            image = self._render_image()
        except PDF_IO_ERRORS as error:
            RENDER_HANDLE_CACHE.invalidate()
            self.signals.failed.emit(
                self._generation,
                self._page_index,
                str(error),
            )
            return

        self.signals.rendered.emit(
            self._generation,
            self._page_index,
            image,
        )

    def _render_image(self) -> QImage:
        """Return the configured thumbnail as a copied Qt image."""
        document = RENDER_HANDLE_CACHE.acquire(
            self._source_path,
            self._render_revision,
        )
        pixmap = render_thumbnail(
            document,
            self._page_index,
            max_dimension=self._max_dimension,
        )
        return qimage_from_pymupdf(pixmap)
