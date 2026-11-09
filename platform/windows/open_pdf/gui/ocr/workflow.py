"""OCR presentation workflow for the active document."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from open_pdf.gui.models.window_state import OcrState
from open_pdf.gui.ocr.task import OcrTask

if TYPE_CHECKING:
    from PySide6.QtCore import QThreadPool
    from PySide6.QtWidgets import QLineEdit, QStatusBar

    from open_pdf.adapters.ocr.backend import PdfOcrBackend
    from open_pdf.adapters.ocr.results import OcrResultStore
    from open_pdf.application.document.session import PdfDocument
    from open_pdf.domains.document.models import PdfOcrPageResult
    from open_pdf.gui.models.window_state import RenderGenerations


class _OcrWorkflowHost(Protocol):
    """Describe the main-window API required by OcrWorkflowMixin."""

    _document: PdfDocument
    _ocr_backend: PdfOcrBackend | None
    _ocr_cache: OcrResultStore
    _ocr_unavailable_message: str | None
    _ocr: OcrState
    _generations: RenderGenerations
    _thread_pool: QThreadPool
    _search_input: QLineEdit

    def _next_generation_token(self) -> int: ...
    def _show_error(self, message: str) -> None: ...
    def _refresh_actions(self) -> None: ...
    def _update_status_bar(self) -> None: ...
    def _run_search(self) -> None: ...
    def _refresh_document_view(self, *, scroll_to_page: bool) -> None: ...
    def statusBar(self) -> QStatusBar: ...  # noqa: N802
    def _handle_ocr_completed(
        self,
        generation: int,
        processed_pages: int,
    ) -> None: ...

    def _handle_ocr_failed(
        self,
        generation: int,
        error_message: str,
    ) -> None: ...

    def _handle_ocr_page_completed(
        self,
        generation: int,
        _page_index: int,
        completed_pages: int,
        total_pages: int,
        result: PdfOcrPageResult,
    ) -> None: ...

    def _start_ocr_request(
        self,
        *,
        page_indexes: tuple[int, ...],
    ) -> None: ...


class OcrWorkflowMixin:
    """Coordinate OCR requests and translate their results into UI updates."""

    def _run_ocr_for_current_page(self: _OcrWorkflowHost) -> None:
        """Run OCR for the currently selected page."""
        if not self._document.has_document():
            return

        self._start_ocr_request(
            page_indexes=(self._document.state.current_page_index,),
        )

    def _run_ocr_for_document(self: _OcrWorkflowHost) -> None:
        """Run OCR for every page in the active document."""
        if not self._document.has_document():
            return

        page_indexes = tuple(range(self._document.state.page_count))
        if not page_indexes:
            return

        self._start_ocr_request(page_indexes=page_indexes)

    def _start_ocr_request(
        self: _OcrWorkflowHost,
        *,
        page_indexes: tuple[int, ...],
    ) -> None:
        """Queue one OCR request for the supplied pages."""
        if not self._document.has_document():
            return

        if self._document.is_dirty():
            self._show_error("Save PDF edits before running OCR.")
            return

        backend = self._ocr_backend
        if backend is None or not self._document.has_ocr_backend():
            self._show_error(
                self._ocr_unavailable_message
                or "OCR is unavailable because no OCR backend is configured.",
            )
            return

        source_path = self._document.source_path
        if source_path is None:
            return

        generation = self._next_generation_token()
        self._generations.ocr = generation
        self._ocr = OcrState(
            active=True,
            completed_pages=0,
            total_pages=len(page_indexes),
        )
        self._refresh_actions()
        self._update_status_bar()

        task = OcrTask(
            source_path=source_path,
            page_indexes=page_indexes,
            generation=generation,
            ocr_backend=backend,
        )
        task.signals.page_completed.connect(self._handle_ocr_page_completed)
        task.signals.failed.connect(self._handle_ocr_failed)
        task.signals.completed.connect(self._handle_ocr_completed)
        self._thread_pool.start(task)

    def _handle_ocr_page_completed(
        self: _OcrWorkflowHost,
        generation: int,
        _page_index: int,
        completed_pages: int,
        total_pages: int,
        result: PdfOcrPageResult,
    ) -> None:
        """Store one OCR result emitted by a background task."""
        if generation != self._generations.ocr:
            return

        self._document.store_ocr_result(result)
        source_path = self._document.source_path
        if source_path is not None:
            self._ocr_cache.save_result(source_path, result)

        self._ocr.completed_pages = completed_pages
        self._ocr.total_pages = total_pages
        self._update_status_bar()

    def _handle_ocr_failed(
        self: _OcrWorkflowHost,
        generation: int,
        error_message: str,
    ) -> None:
        """Report a failed OCR request and clear OCR progress state."""
        if generation != self._generations.ocr:
            return

        self._ocr = OcrState()
        self._refresh_actions()
        self._update_status_bar()
        self._show_error(f"Failed to run OCR:\n{error_message}")

    def _handle_ocr_completed(
        self: _OcrWorkflowHost,
        generation: int,
        processed_pages: int,
    ) -> None:
        """Refresh the UI after one OCR request completes."""
        if generation != self._generations.ocr:
            return

        self._ocr = OcrState()
        if self._search_input.text().strip():
            self._run_search()
        else:
            self._refresh_document_view(scroll_to_page=False)
            self._refresh_actions()
        self._update_status_bar()
        page_word = "page" if processed_pages == 1 else "pages"
        self.statusBar().showMessage(
            f"OCR completed for {processed_pages} {page_word}.",
            5000,
        )
