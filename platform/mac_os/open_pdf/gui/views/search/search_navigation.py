"""Search command and result navigation behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from open_pdf.adapters.document.errors import PDF_IO_ERRORS
from open_pdf.gui.views.search.search_task import SearchTask

if TYPE_CHECKING:
    from PySide6.QtCore import QThreadPool
    from PySide6.QtWidgets import QLineEdit, QStatusBar

    from open_pdf.application.document.session import PdfDocument
    from open_pdf.domains.document.models import PdfSearchMatch, Rectangle
    from open_pdf.gui.models.window_state import RenderGenerations, SearchState


class _SearchNavigationHost(Protocol):
    """Describe the main-window API required by SearchNavigationMixin."""

    _document: PdfDocument
    _search_input: QLineEdit
    _search: SearchState
    _generations: RenderGenerations
    _thread_pool: QThreadPool

    def _show_error(self, message: str) -> None: ...
    def _refresh_document_view(self, *, scroll_to_page: bool) -> None: ...
    def _sync_current_page_ui(self, *, scroll_to_page: bool) -> None: ...
    def _refresh_actions(self) -> None: ...
    def _update_search_bar_state(self) -> None: ...
    def statusBar(self) -> QStatusBar: ...  # noqa: N802
    def _clear_search_results(self) -> None: ...

    def _handle_search_completed(
        self,
        generation: int,
        query: str,
        matches: list[PdfSearchMatch],
    ) -> None: ...

    def _handle_search_failed(
        self,
        generation: int,
        _query: str,
        error_message: str,
    ) -> None: ...

    def _jump_to_current_match(self) -> None: ...

    def _nearest_search_match_index(self) -> int: ...

    def _run_dirty_document_search(
        self,
        *,
        query: str,
        generation: int,
    ) -> None: ...


class SearchNavigationMixin:
    """Run searches and move between search results."""

    def _run_search(self: _SearchNavigationHost) -> None:
        if not self._document.has_document():
            return

        query = self._search_input.text().strip()
        if not query:
            self._clear_search_results()
            self._refresh_document_view(scroll_to_page=False)
            self._refresh_actions()
            return

        source_path = self._document.source_path
        if source_path is None:
            return

        self._generations.search += 1
        self.statusBar().showMessage(f'Searching for "{query}"...')
        if self._document.is_dirty() or self._document.has_ocr_results():
            self._run_dirty_document_search(
                query=query,
                generation=self._generations.search,
            )
            return

        task = SearchTask(
            source_path=source_path,
            query=query,
            generation=self._generations.search,
        )
        task.signals.completed.connect(self._handle_search_completed)
        task.signals.failed.connect(self._handle_search_failed)
        self._thread_pool.start(task)

    def _run_dirty_document_search(
        self: _SearchNavigationHost,
        *,
        query: str,
        generation: int,
    ) -> None:
        try:
            matches = self._document.search(query)
        except PDF_IO_ERRORS as error:
            self._handle_search_failed(generation, query, str(error))
            return

        self._handle_search_completed(generation, query, matches)

    def _handle_search_completed(
        self: _SearchNavigationHost,
        generation: int,
        query: str,
        matches: list[PdfSearchMatch],
    ) -> None:
        if generation != self._generations.search:
            return

        self._search.matches = matches
        self._search.rectangles_by_page = {
            match.page_index: match.rectangles for match in matches
        }
        self._search.last_query = query

        if not matches:
            self._search.match_index = -1
            self._refresh_document_view(scroll_to_page=False)
            self._refresh_actions()
            self.statusBar().showMessage(
                f'No matches found for "{query}".',
                5000,
            )
            return

        self._search.match_index = self._nearest_search_match_index()
        self._refresh_document_view(scroll_to_page=False)
        self._jump_to_current_match()
        self._refresh_actions()

    def _handle_search_failed(
        self: _SearchNavigationHost,
        generation: int,
        _query: str,
        error_message: str,
    ) -> None:
        if generation != self._generations.search:
            return

        self._show_error(f"Failed to search PDF:\n{error_message}")

    def _show_previous_match(self: _SearchNavigationHost) -> None:
        if not self._search.matches:
            return

        self._search.match_index = (self._search.match_index - 1) % len(
            self._search.matches,
        )
        self._jump_to_current_match()
        self._update_search_bar_state()

    def _show_next_match(self: _SearchNavigationHost) -> None:
        if not self._search.matches:
            return

        self._search.match_index = (self._search.match_index + 1) % len(
            self._search.matches,
        )
        self._jump_to_current_match()
        self._update_search_bar_state()

    def _search_rectangles_for_page(
        self: _SearchNavigationHost,
        page_index: int,
    ) -> tuple[Rectangle, ...]:
        return self._search.rectangles_by_page.get(page_index, ())

    def _jump_to_current_match(self: _SearchNavigationHost) -> None:
        if not self._search.matches or self._search.match_index < 0:
            return

        match = self._search.matches[self._search.match_index]
        self._document.go_to_page(match.page_index)
        self._sync_current_page_ui(scroll_to_page=True)

    def _nearest_search_match_index(self: _SearchNavigationHost) -> int:
        current_page_index = self._document.state.current_page_index
        for index, match in enumerate(self._search.matches):
            if match.page_index >= current_page_index:
                return index

        return 0

    def _clear_search_results(self: _SearchNavigationHost) -> None:
        self._generations.search += 1
        self._search.last_query = ""
        self._search.matches = []
        self._search.match_index = -1
        self._search.rectangles_by_page = {}
        self._update_search_bar_state()
