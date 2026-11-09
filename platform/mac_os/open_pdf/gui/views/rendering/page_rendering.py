"""Background page rendering tasks for the PySide6 PDF view."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRunnable, Signal

from open_pdf.adapters.document.errors import PDF_IO_ERRORS
from open_pdf.adapters.document.pymupdf.qt import qimage_from_pymupdf
from open_pdf.adapters.document.pymupdf.rendering import render_page
from open_pdf.gui.views.rendering.render_handle_cache import RENDER_HANDLE_CACHE

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from PySide6.QtGui import QImage


class _CancelledPageRenderError(RuntimeError):
    """Raised when a queued page render is no longer current."""


class PageRenderSignals(QObject):
    """Signals emitted by one background page render task."""

    rendered = Signal(int, int, int, object)
    failed = Signal(int, int, int, str)
    cancelled = Signal(int, int, int)


@dataclass(slots=True)
class PageRenderRequest:
    """Store the inputs required for one background page render."""

    source_path: Path
    render_revision: int
    page_index: int
    zoom: float
    device_pixel_ratio: float
    generation: int
    request_token: int
    is_still_current: Callable[[int, int, int], bool]


class PageRenderTask(QRunnable):
    """Render one PDF page into a detached Qt image."""

    def __init__(
        self,
        *,
        request: PageRenderRequest,
    ) -> None:
        """Store the inputs for one background render job."""
        super().__init__()
        self._request = request
        self.signals = PageRenderSignals()

    def run(self) -> None:
        """Render the configured page and emit the result."""
        try:
            image = self._render_image()
        except _CancelledPageRenderError:
            self.signals.cancelled.emit(
                self._request.generation,
                self._request.page_index,
                self._request.request_token,
            )
            return
        except PDF_IO_ERRORS as error:
            RENDER_HANDLE_CACHE.invalidate()
            self.signals.failed.emit(
                self._request.generation,
                self._request.page_index,
                self._request.request_token,
                str(error),
            )
            return

        if self._is_stale():
            self.signals.cancelled.emit(
                self._request.generation,
                self._request.page_index,
                self._request.request_token,
            )
            return

        self.signals.rendered.emit(
            self._request.generation,
            self._request.page_index,
            self._request.request_token,
            image,
        )

    def _is_stale(self) -> bool:
        return not self._request.is_still_current(
            self._request.generation,
            self._request.page_index,
            self._request.request_token,
        )

    def _render_image(self) -> QImage:
        """Return the configured page as a copied Qt image."""
        if self._is_stale():
            raise _CancelledPageRenderError

        document = RENDER_HANDLE_CACHE.acquire(
            self._request.source_path,
            self._request.render_revision,
        )
        if self._is_stale():
            raise _CancelledPageRenderError

        pixmap = render_page(
            document,
            self._request.page_index,
            zoom=self._request.zoom,
            device_pixel_ratio=self._request.device_pixel_ratio,
        )
        if self._is_stale():
            raise _CancelledPageRenderError

        image = qimage_from_pymupdf(pixmap)
        image.setDevicePixelRatio(self._request.device_pixel_ratio)
        return image
