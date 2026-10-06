"""Document-tab presentation and per-tab session coordination."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import QMainWindow, QTabBar, QToolBar

from src.gui.models.document_session import DocumentSession
from src.gui.models.window_state import OcrState, SearchState

if TYPE_CHECKING:
    from pathlib import Path

    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QLineEdit, QWidget

    from src.domains.document.reader import PdfDocument
    from src.gui.models.window_state import RenderGenerations, SyncGuards


class _DocumentTabsHost(Protocol):
    """Describe the main-window API required by DocumentTabsMixin."""

    _document: PdfDocument
    _tab_sessions: list[DocumentSession]
    _active_tab_index: int
    _search: SearchState
    _ocr: OcrState
    _generations: RenderGenerations
    _sync: SyncGuards
    _search_bar: QWidget
    _search_input: QLineEdit
    _single_page_view_enabled: bool
    _single_page_view_action: QAction
    _document_tabs: QTabBar
    _document_tabs_toolbar: QToolBar

    def _new_document_reader(self) -> PdfDocument: ...
    def _reset_render_request_scope(self) -> None: ...
    def _clear_page_labels(self) -> None: ...
    def _populate_bookmarks(self) -> None: ...
    def _populate_thumbnails(self) -> None: ...
    def _refresh_document_view(self, *, scroll_to_page: bool) -> None: ...
    def _confirm_unsaved_changes(self) -> bool: ...
    def _open_document(self, path: Path) -> bool: ...
    # Positional-only: Qt declares setWindowTitle with an unnamed
    # parameter, and a named parameter here fails the protocol.
    def setWindowTitle(self, title: str, /) -> None:  # noqa: N802
        """Set the native window title."""

    def isMinimized(self) -> bool:  # noqa: N802
        """Return whether the window is minimized."""
        ...

    def showNormal(self) -> None:  # noqa: N802
        """Restore the window to its normal state."""

    def show(self) -> None:
        """Show the window."""

    def raise_(self) -> None:
        """Raise the window above other windows."""

    def activateWindow(self) -> None:  # noqa: N802
        """Activate the window."""

    def _activate_document_tab(self, index: int) -> None: ...

    def _append_empty_tab(self) -> int: ...

    def _capture_active_tab_session(self) -> DocumentSession: ...

    def _close_document_tab(self, index: int) -> None: ...

    def _find_tab_index_for_path(
        self,
        path: Path,
    ) -> int | None: ...

    def _handle_document_tab_changed(
        self,
        index: int,
    ) -> None: ...

    def _handle_document_tab_moved(
        self,
        from_index: int,
        to_index: int,
    ) -> None: ...

    def _next_generation_token(self) -> int: ...

    @staticmethod
    def _normalize_document_path(path: Path) -> Path: ...

    def _open_path_in_tab(self, path: Path) -> None: ...

    def _restore_active_tab_session(
        self,
        session: DocumentSession,
    ) -> None: ...

    def _retire_async_generations(self) -> None: ...

    def _store_active_tab_session(self) -> None: ...

    def _sync_active_tab_caption(self) -> None: ...

    def _tab_title_for_session(
        self,
        session: DocumentSession,
    ) -> str: ...

    def _update_window_title(self) -> None: ...


class DocumentTabsMixin:
    """Coordinate document tabs and their presentation sessions."""

    def _build_document_tabs(self: _DocumentTabsHost) -> None:
        """Build the document tabs row shown beneath the main tool bar."""
        document_tabs = QTabBar()
        document_tabs.setDocumentMode(True)
        document_tabs.setDrawBase(False)
        document_tabs.setExpanding(False)
        document_tabs.setMovable(True)
        document_tabs.setTabsClosable(True)
        document_tabs.currentChanged.connect(self._handle_document_tab_changed)
        document_tabs.tabCloseRequested.connect(self._close_document_tab)
        document_tabs.tabMoved.connect(self._handle_document_tab_moved)
        self._document_tabs = document_tabs

        tabs_toolbar = QToolBar("Documents")
        tabs_toolbar.setObjectName("document-tabs-toolbar")
        tabs_toolbar.setMovable(False)
        tabs_toolbar.addWidget(document_tabs)
        self._document_tabs_toolbar = tabs_toolbar

        window = cast("QMainWindow", self)
        window.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        window.addToolBar(Qt.ToolBarArea.TopToolBarArea, tabs_toolbar)

    def _initialize_document_tabs(self: _DocumentTabsHost) -> None:
        """Seed the shell with one empty tab session."""
        initial_session = self._capture_active_tab_session()
        self._tab_sessions = [initial_session]
        self._active_tab_index = 0
        self._document_tabs.addTab(self._tab_title_for_session(initial_session))
        self._document_tabs.setCurrentIndex(0)
        self._sync_active_tab_caption()

    def _capture_active_tab_session(self: _DocumentTabsHost) -> DocumentSession:
        """Snapshot the active document state before leaving a tab."""
        return DocumentSession(
            document=self._document,
            search_matches=list(self._search.matches),
            search_match_index=self._search.match_index,
            search_rectangles_by_page=dict(self._search.rectangles_by_page),
            last_search_query=self._search.last_query,
            search_bar_visible=not self._search_bar.isHidden(),
            search_text=self._search_input.text(),
            single_page_view_enabled=self._single_page_view_enabled,
        )

    def _store_active_tab_session(self: _DocumentTabsHost) -> None:
        """Persist the active tab's session before switching away from it."""
        if 0 <= self._active_tab_index < len(self._tab_sessions):
            self._tab_sessions[self._active_tab_index] = (
                self._capture_active_tab_session()
            )

    def _restore_active_tab_session(
        self: _DocumentTabsHost,
        session: DocumentSession,
    ) -> None:
        """Load one tab session into the shared viewer surface."""
        self._document = session.document
        self._single_page_view_enabled = session.single_page_view_enabled
        self._search = SearchState(
            matches=list(session.search_matches),
            match_index=session.search_match_index,
            rectangles_by_page=dict(session.search_rectangles_by_page),
            last_query=session.last_search_query,
        )
        self._retire_async_generations()
        self._clear_page_labels()

        search_input_blocker = QSignalBlocker(self._search_input)
        self._search_input.setText(session.search_text)
        del search_input_blocker

        self._search_bar.setVisible(
            session.search_bar_visible and self._document.has_document(),
        )
        action_blocker = QSignalBlocker(self._single_page_view_action)
        self._single_page_view_action.setChecked(
            self._single_page_view_enabled,
        )
        del action_blocker
        self._populate_bookmarks()
        self._populate_thumbnails()
        self._refresh_document_view(scroll_to_page=False)

    def _retire_async_generations(self: _DocumentTabsHost) -> None:
        """Invalidate background results produced for another tab session."""
        self._generations.ocr = self._next_generation_token()
        self._generations.search = self._next_generation_token()
        self._generations.thumbnail = self._next_generation_token()
        self._generations.render = self._next_generation_token()
        self._reset_render_request_scope()
        self._ocr = OcrState()

    def _next_generation_token(self: _DocumentTabsHost) -> int:
        """Return a process-unique generation token for async tasks."""
        self._generations.counter += 1
        return self._generations.counter

    def _handle_document_tab_changed(
        self: _DocumentTabsHost,
        index: int,
    ) -> None:
        """Swap the active document session when the selected tab changes."""
        if self._sync.switching_document_tabs or index < 0:
            return

        if index == self._active_tab_index:
            return

        self._store_active_tab_session()
        self._active_tab_index = index
        self._restore_active_tab_session(self._tab_sessions[index])

    def _handle_document_tab_moved(
        self: _DocumentTabsHost,
        from_index: int,
        to_index: int,
    ) -> None:
        """Keep session ordering aligned with the visual tab order."""
        if not 0 <= from_index < len(self._tab_sessions):
            return
        if not 0 <= to_index < len(self._tab_sessions):
            return

        self._store_active_tab_session()
        moved_session = self._tab_sessions.pop(from_index)
        self._tab_sessions.insert(to_index, moved_session)
        self._active_tab_index = self._document_tabs.currentIndex()
        self._sync_active_tab_caption()

    def _activate_document_tab(self: _DocumentTabsHost, index: int) -> None:
        """Make one tab the active document session."""
        if not 0 <= index < len(self._tab_sessions):
            return

        if self._document_tabs.currentIndex() != index:
            self._document_tabs.setCurrentIndex(index)
            return

        if index != self._active_tab_index:
            self._handle_document_tab_changed(index)

    def _close_document_tab(self: _DocumentTabsHost, index: int) -> None:
        """Close one tab, prompting when its document has unsaved changes."""
        if not 0 <= index < len(self._tab_sessions):
            return

        if index != self._active_tab_index:
            self._activate_document_tab(index)
        if index != self._active_tab_index:
            return

        if not self._confirm_unsaved_changes():
            return

        self._document.close_document()
        self._tab_sessions.pop(index)

        self._sync.switching_document_tabs = True
        try:
            self._document_tabs.removeTab(index)
            if not self._tab_sessions:
                blank_session = DocumentSession(
                    document=self._new_document_reader(),
                )
                self._tab_sessions.append(blank_session)
                self._document_tabs.addTab(
                    self._tab_title_for_session(blank_session),
                )
                next_index = 0
            else:
                next_index = min(index, len(self._tab_sessions) - 1)

            self._document_tabs.setCurrentIndex(next_index)
        finally:
            self._sync.switching_document_tabs = False

        self._active_tab_index = next_index
        self._restore_active_tab_session(self._tab_sessions[next_index])

    def _close_current_tab(self: _DocumentTabsHost) -> None:
        """Close the currently selected tab from the File menu."""
        current_index = self._document_tabs.currentIndex()
        if current_index < 0:
            return

        self._close_document_tab(current_index)

    def _tab_title_for_session(
        self: _DocumentTabsHost,
        session: DocumentSession,
    ) -> str:
        """Return the label shown for one document tab."""
        source_path = session.document.source_path
        base_title = source_path.name if source_path is not None else "Start"
        if source_path is not None:
            duplicate_count = sum(
                1
                for tab_session in self._tab_sessions
                if tab_session.document.source_path is not None
                and tab_session.document.source_path.name == source_path.name
            )
            if duplicate_count > 1:
                base_title = str(source_path)
        if session.document.is_dirty():
            return f"* {base_title}"

        return base_title

    def _sync_active_tab_caption(self: _DocumentTabsHost) -> None:
        """Refresh all tab captions and the top-level window title.

        - Reads live state directly; the active tab's stored session shares
          its document object with ``self._document``, so no per-refresh
          session capture is needed. Session persistence happens explicitly
          via :meth:`_store_active_tab_session` on tab switch/move/close.
        """
        for index, session in enumerate(self._tab_sessions):
            self._document_tabs.setTabText(
                index,
                self._tab_title_for_session(session),
            )
            source_path = session.document.source_path
            self._document_tabs.setTabToolTip(
                index,
                str(source_path)
                if source_path is not None
                else "No PDF loaded",
            )

        self._update_window_title()

    def _update_window_title(self: _DocumentTabsHost) -> None:
        """Reflect the active tab in the top-level window title."""
        source_path = self._document.source_path
        if source_path is None:
            self.setWindowTitle("Open PDF")
            return

        dirty_prefix = "* " if self._document.is_dirty() else ""
        self.setWindowTitle(f"Open PDF - {dirty_prefix}{source_path.name}")

    @staticmethod
    def _normalize_document_path(path: Path) -> Path:
        """Normalize paths before tab lookup or document open."""
        return path.expanduser().resolve(strict=False)

    def _find_tab_index_for_path(
        self: _DocumentTabsHost,
        path: Path,
    ) -> int | None:
        """Return the index of the existing tab for `path`, when present."""
        normalized_path = self._normalize_document_path(path)
        for index, session in enumerate(self._tab_sessions):
            source_path = session.document.source_path
            if source_path is None:
                continue
            if self._normalize_document_path(source_path) == normalized_path:
                return index

        return None

    def _append_empty_tab(self: _DocumentTabsHost) -> int:
        """Create a new blank tab session and return its index."""
        blank_session = DocumentSession(
            document=self._new_document_reader(),
        )
        self._tab_sessions.append(blank_session)
        return self._document_tabs.addTab(
            self._tab_title_for_session(blank_session),
        )

    def _open_path_in_tab(self: _DocumentTabsHost, path: Path) -> None:
        """Open one PDF, reusing an empty tab or creating a new one."""
        existing_index = self._find_tab_index_for_path(path)
        if existing_index is not None:
            self._activate_document_tab(existing_index)
            return

        created_tab_index: int | None = None
        if self._document.has_document():
            self._store_active_tab_session()
            new_index = self._append_empty_tab()
            self._activate_document_tab(new_index)
            created_tab_index = new_index

        if self._open_document(self._normalize_document_path(path)):
            return

        if created_tab_index is not None:
            self._close_document_tab(created_tab_index)

    def open_document_in_tab(self: _DocumentTabsHost, path: Path) -> None:
        """Open one PDF in the current process, creating a tab when needed."""
        self._open_path_in_tab(path)

    def present(self: _DocumentTabsHost) -> None:
        """Raise and focus the existing window for single-instance launches."""
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
