"""Document view refresh and widget synchronization behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import Qt

from src.domains.document.errors import PDF_IO_ERRORS
from src.gui.views.rendering.page_metrics import PAGE_CONTENT_CHROME
from src.gui.views.rendering.page_surface import PageSurfaceLabel

if TYPE_CHECKING:
    from threading import Lock

    from PySide6.QtWidgets import (
        QLabel,
        QListWidget,
        QScrollArea,
        QSpinBox,
        QTextEdit,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    from src.domains.document.pages.history import ScrollState
    from src.domains.document.reader import PdfDocument
    from src.gui.models.window_state import RenderGenerations, SyncGuards


_PAGE_SCROLL_TARGET_MARGIN = 40


class _DocumentSyncHost(Protocol):
    """Describe the main-window API required by DocumentSyncMixin."""

    _document: PdfDocument
    _empty_state_label: QLabel
    _bookmark_tree: QTreeWidget
    _thumbnail_list: QListWidget
    _page_text: QTextEdit
    _notes_text: QTextEdit
    _document_layout: QVBoxLayout
    _document_container: QWidget
    _page_labels: list[QLabel]
    _visible_page_indexes: list[int]
    _rendered_page_indexes: set[int]
    _pending_page_indexes: dict[int, int]
    _desired_page_indexes: set[int]
    _render_request_lock: Lock
    _words_loaded_pages: set[int]
    _generations: RenderGenerations
    _sync: SyncGuards
    _page_selector: QSpinBox
    _document_scroll_area: QScrollArea
    _single_page_view_enabled: bool

    _highlighted_page_index: int | None

    def _refresh_actions(self) -> None: ...
    def _update_status_bar(self) -> None: ...
    def _show_error(self, message: str) -> None: ...
    def _refresh_visible_pages(self) -> None: ...
    def _update_current_page_highlight(self) -> None: ...
    def _update_text_panel(self) -> None: ...
    def _visible_page_index(self) -> int | None: ...
    def _rebuild_page_geometry_cache(self) -> None: ...
    def _clear_page_geometry_cache(self) -> None: ...
    def _reset_render_request_scope(self) -> None: ...
    def _cancel_zoom_preview(self) -> None: ...
    def _apply_default_page_border(self, page_label: QLabel) -> None: ...
    def _configure_page_surface(
        self,
        page_label: PageSurfaceLabel,
        page_index: int,
    ) -> None: ...
    def _find_bookmark_item_for_page(
        self,
        page_index: int,
    ) -> QTreeWidgetItem | None: ...

    @staticmethod
    def _page_placeholder_text(page_index: int) -> str: ...
    def _build_page_placeholders(self) -> None: ...

    def _clear_page_labels(self) -> None: ...

    def _page_indexes_for_current_view(self) -> list[int]: ...

    def _scroll_to_current_page(self) -> None: ...

    def _single_page_view_needs_rebuild(self) -> bool: ...

    def _sync_bookmark_selection(self) -> None: ...

    def _sync_current_page_ui(
        self,
        *,
        scroll_to_page: bool,
    ) -> None: ...

    def _sync_page_selector(self) -> None: ...

    def _sync_thumbnail_selection(self) -> None: ...

    def _current_scroll_pdf_point(
        self,
    ) -> tuple[float | None, float | None]: ...

    def _scroll_to_page_position(
        self,
        *,
        page_index: int,
        position: tuple[float, float] | None,
    ) -> None: ...


class DocumentSyncMixin:
    """Synchronize the active document with visible widgets."""

    if TYPE_CHECKING:
        # Declared so the type matches _DocumentSyncHost rather than
        # being inferred as None from the assignment below.
        _highlighted_page_index: int | None

    def _refresh_document_view(
        self: _DocumentSyncHost,
        *,
        scroll_to_page: bool,
    ) -> None:
        if not self._document.has_document():
            self._clear_page_labels()
            self._empty_state_label.show()
            self._bookmark_tree.clearSelection()
            self._thumbnail_list.clearSelection()
            self._page_text.clear()
            self._sync.notes_text = True
            self._notes_text.clear()
            self._sync.notes_text = False
            self._notes_text.setEnabled(False)
            self._refresh_actions()
            self._update_status_bar()
            return

        try:
            self._build_page_placeholders()
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to render page:\n{error}")
            return

        self._sync_current_page_ui(scroll_to_page=scroll_to_page)

        self._sync.notes_text = True
        self._notes_text.setPlainText(self._document.notes_text())
        self._notes_text.setEnabled(True)
        self._sync.notes_text = False

    def _build_page_placeholders(self: _DocumentSyncHost) -> None:
        self._empty_state_label.hide()
        self._clear_page_labels()
        self._generations.render += 1
        self._reset_render_request_scope()
        self._visible_page_indexes = self._page_indexes_for_current_view()

        for page_index in self._visible_page_indexes:
            page_width, page_height = self._document.page_display_size(
                page_index,
            )
            page_label = PageSurfaceLabel()
            page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            page_label.setText(self._page_placeholder_text(page_index))
            page_label.set_page_zoom(zoom=self._document.state.zoom)
            page_label.setFixedSize(
                page_width + PAGE_CONTENT_CHROME,
                page_height + PAGE_CONTENT_CHROME,
            )
            self._apply_default_page_border(page_label)
            self._configure_page_surface(
                page_label,
                page_index,
            )
            self._document_layout.addWidget(
                page_label,
                alignment=Qt.AlignmentFlag.AlignHCenter,
            )
            self._page_labels.append(page_label)

        self._document_layout.activate()
        self._document_container.adjustSize()
        self._rebuild_page_geometry_cache()

    def _clear_page_labels(self: _DocumentSyncHost) -> None:
        # Preview gesture state points at labels that are about to go away.
        self._cancel_zoom_preview()
        for page_label in self._page_labels:
            self._document_layout.removeWidget(page_label)
            page_label.deleteLater()
        self._page_labels.clear()
        self._visible_page_indexes.clear()
        self._rendered_page_indexes.clear()
        self._desired_page_indexes.clear()
        self._reset_render_request_scope()
        self._words_loaded_pages.clear()
        self._clear_page_geometry_cache()
        self._highlighted_page_index = None

    def _sync_current_page_ui(
        self: _DocumentSyncHost,
        *,
        scroll_to_page: bool,
    ) -> None:
        if not self._document.has_document():
            return

        if self._single_page_view_needs_rebuild():
            self._build_page_placeholders()

        self._refresh_visible_pages()
        self._update_current_page_highlight()
        self._sync_page_selector()
        self._sync_thumbnail_selection()
        self._sync_bookmark_selection()
        self._update_text_panel()
        self._refresh_actions()
        self._update_status_bar()
        if scroll_to_page:
            self._scroll_to_current_page()

    def _handle_document_scrolled(self: _DocumentSyncHost, _value: int) -> None:
        if self._sync.scroll_position or not self._document.has_document():
            return

        self._refresh_visible_pages()
        visible_page_index = self._visible_page_index()
        if visible_page_index is None:
            return

        if visible_page_index == self._document.state.current_page_index:
            return

        self._document.go_to_page(visible_page_index, record_history=False)
        self._sync_current_page_ui(scroll_to_page=False)

    def _sync_page_selector(self: _DocumentSyncHost) -> None:
        state = self._document.state
        self._sync.page_selector = True
        self._page_selector.setMaximum(max(state.page_count, 1))
        self._page_selector.setValue(max(state.current_page_index + 1, 1))
        self._sync.page_selector = False

    def _sync_thumbnail_selection(self: _DocumentSyncHost) -> None:
        self._sync.thumbnail_list = True
        self._thumbnail_list.setCurrentRow(
            self._document.state.current_page_index,
        )
        current_item = self._thumbnail_list.currentItem()
        if current_item is not None:
            self._thumbnail_list.scrollToItem(current_item)
        self._sync.thumbnail_list = False

    def _sync_bookmark_selection(self: _DocumentSyncHost) -> None:
        matched_item = self._find_bookmark_item_for_page(
            self._document.state.current_page_index,
        )
        if matched_item is None:
            self._bookmark_tree.clearSelection()
            return

        self._bookmark_tree.setCurrentItem(matched_item)
        self._bookmark_tree.scrollToItem(matched_item)

    def _scroll_to_current_page(self: _DocumentSyncHost) -> None:
        if not self._page_labels:
            return

        current_label = self._page_labels[
            self._visible_page_indexes.index(
                self._document.state.current_page_index,
            )
        ]
        self._sync.scroll_position = True
        self._document_scroll_area.ensureWidgetVisible(
            current_label,
            0,
            _PAGE_SCROLL_TARGET_MARGIN,
        )
        self._sync.scroll_position = False
        self._refresh_visible_pages()

    def _current_scroll_pdf_point(
        self: _DocumentSyncHost,
    ) -> tuple[float | None, float | None]:
        """Return the viewport's top-left in PDF units for the current page.

        - Returns (None, None) when the current page is not laid out, so
          history falls back to a page-only entry.
        """
        page_index = self._document.state.current_page_index
        if page_index not in self._visible_page_indexes:
            return (None, None)

        page_label = self._page_labels[
            self._visible_page_indexes.index(page_index)
        ]
        inset = PAGE_CONTENT_CHROME / 2
        horizontal_bar = self._document_scroll_area.horizontalScrollBar()
        vertical_bar = self._document_scroll_area.verticalScrollBar()
        display_position = (
            horizontal_bar.value() - page_label.x() - inset,
            vertical_bar.value() - page_label.y() - inset,
        )
        pdf_point = self._document.pdf_point_for_display_position(
            page_index=page_index,
            position=display_position,
        )
        if pdf_point is None:
            return (None, None)

        return pdf_point

    def _record_history_scroll_position(self: _DocumentSyncHost) -> None:
        """Snapshot where the reader is, so back/forward returns here."""
        if not self._document.has_document():
            return

        x_pdf, y_pdf = self._current_scroll_pdf_point()
        self._document.record_history_position(x_pdf=x_pdf, y_pdf=y_pdf)

    def _restore_history_scroll_state(
        self: _DocumentSyncHost,
        state: ScrollState | None,
    ) -> None:
        """Scroll to a restored history entry's recorded position."""
        self._sync_current_page_ui(scroll_to_page=state is None)
        if state is None or state.x_pdf is None or state.y_pdf is None:
            return

        display = self._document.page_link_target_position(
            target_page_index=state.page_index,
            target_point=(state.x_pdf, state.y_pdf),
        )
        if display is None:
            return

        self._scroll_to_page_position(
            page_index=state.page_index,
            position=display,
        )

    def _scroll_to_page_position(
        self: _DocumentSyncHost,
        *,
        page_index: int,
        position: tuple[float, float] | None,
    ) -> None:
        if position is None:
            self._scroll_to_current_page()
            return

        if page_index not in self._visible_page_indexes:
            return

        current_label = self._page_labels[
            self._visible_page_indexes.index(page_index)
        ]
        viewport = self._document_scroll_area.viewport()
        horizontal_bar = self._document_scroll_area.horizontalScrollBar()
        vertical_bar = self._document_scroll_area.verticalScrollBar()
        inset = PAGE_CONTENT_CHROME / 2

        content_x = current_label.x() + inset + position[0]
        content_y = current_label.y() + inset + position[1]
        horizontal_target = max(
            round(content_x - _PAGE_SCROLL_TARGET_MARGIN),
            0,
        )
        vertical_target = max(
            round(content_y - _PAGE_SCROLL_TARGET_MARGIN),
            0,
        )

        self._sync.scroll_position = True
        horizontal_bar.setValue(
            min(horizontal_target, horizontal_bar.maximum()),
        )
        vertical_bar.setValue(min(vertical_target, vertical_bar.maximum()))
        self._sync.scroll_position = False
        viewport.update()
        self._refresh_visible_pages()

    def _page_indexes_for_current_view(self: _DocumentSyncHost) -> list[int]:
        if not self._document.has_document():
            return []

        if self._single_page_view_enabled:
            return [self._document.state.current_page_index]

        return list(range(self._document.state.page_count))

    def _single_page_view_needs_rebuild(self: _DocumentSyncHost) -> bool:
        return (
            self._single_page_view_enabled
            and self._visible_page_indexes
            != [self._document.state.current_page_index]
        )
