"""Bookmark navigation behavior for the PySide6 PDF window."""

from __future__ import annotations

import logging
from bisect import bisect_right
from functools import partial
from typing import TYPE_CHECKING, Protocol, cast

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from src.domains.document.errors import PDF_IO_ERRORS
from src.gui.views.rendering.page_surface import PageSurfaceLabel
from src.gui.views.root_window.navigation.page_links import (
    PageLinkNavigationMixin,
)

if TYPE_CHECKING:
    from pathlib import Path

    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QScrollArea, QStatusBar, QToolButton

    from src.domains.document.models import (
        PdfOutlineItem,
        PdfPageLink,
        PdfTextSpan,
    )
    from src.domains.document.reader import PdfDocument
    from src.gui.models.window_state import SyncGuards


logger = logging.getLogger(__name__)

_BOOKMARK_TITLE_LIMIT = 80


class _BookmarkNavigationHost(Protocol):
    """Describe the main-window API required by BookmarkNavigationMixin."""

    _document: PdfDocument
    _bookmark_tree: QTreeWidget
    _page_text: QTextEdit
    _page_labels: list[QLabel]
    _visible_page_indexes: list[int]
    _is_text_selection_mode: bool
    _is_pdf_edit_mode: bool
    _browse_mouse_mode_action: QAction
    _text_selection_mouse_mode_action: QAction
    _mouse_mode_indicator: QToolButton
    _bookmark_item_by_page: dict[int, QTreeWidgetItem]
    _bookmark_pages_sorted: list[int]
    _rendered_page_indexes: set[int]
    _words_loaded_pages: set[int]
    _document_scroll_area: QScrollArea
    _sync: SyncGuards
    # Holds a strong reference to the page-surface context menu while it is
    # open, and is cleared back to None when the menu hides.
    _active_page_surface_context_menu: QMenu | None

    def _handle_page_link_activated(self, link: PdfPageLink) -> None: ...

    def _sync_current_page_ui(
        self,
        *,
        scroll_to_page: bool,
    ) -> None: ...
    def _scroll_to_page_position(
        self,
        *,
        page_index: int,
        position: tuple[float, float] | None,
    ) -> None: ...

    def _refresh_actions(self) -> None: ...

    def _clear_search_results(self) -> None: ...

    def _persist_pane_visibility_settings(self) -> None: ...

    def _populate_thumbnails(self) -> None: ...

    def _refresh_document_view(
        self,
        *,
        scroll_to_page: bool,
    ) -> None: ...

    def _refresh_visible_pages(self) -> None: ...

    def _show_error(self, message: str) -> None: ...

    def statusBar(self) -> QStatusBar: ...  # noqa: N802

    def _label_index_for_page(
        self,
        page_index: int | None,
    ) -> int | None: ...
    def _apply_zoom(
        self,
        target_zoom: float,
        *,
        anchor_position: QPointF | None = None,
    ) -> None: ...

    def open_document_in_tab(self, path: Path) -> None:
        """Open one PDF in a tab within the current window."""
        ...

    def _add_bookmark_from_selected_text(
        self,
        title: str | None = None,
        *,
        page_index: int | None = None,
    ) -> None: ...

    def _apply_context_menu_theme(
        self,
        menu: QMenu,
        *,
        source_widget: QWidget,
    ) -> None: ...

    def _apply_text_selection_mode(self) -> None: ...

    def _bookmark_title_from_text(
        self,
        selected_text: str,
    ) -> str | None: ...

    def _clear_bookmark_page_cache(self) -> None: ...

    def _delete_bookmark_item(
        self,
        item: QTreeWidgetItem,
        *,
        toc_index: int,
    ) -> None: ...

    def _ensure_page_words_loaded(
        self,
        page_index: int,
    ) -> None: ...

    def _insert_bookmark_item(
        self,
        *,
        tree_item: QTreeWidgetItem,
        outline_item: PdfOutlineItem,
        parent_stack: dict[int, QTreeWidgetItem],
    ) -> None: ...

    def _populate_bookmarks(self) -> None: ...

    def _prompt_for_bookmark_title(
        self,
        current_title: str,
    ) -> str | None: ...

    def _rebuild_bookmark_page_cache(self) -> None: ...

    def _remove_selected_text(
        self,
        *,
        page_index: int | None = None,
        page_label: PageSurfaceLabel | None = None,
    ) -> None: ...

    def _rename_bookmark_item(
        self,
        item: QTreeWidgetItem,
        *,
        toc_index: int,
    ) -> None: ...

    def _replace_selected_text(
        self,
        *,
        page_index: int | None = None,
        page_label: PageSurfaceLabel | None = None,
    ) -> None: ...

    def _apply_text_span_replacement(
        self,
        *,
        span: PdfTextSpan,
        replacement: str,
    ) -> None: ...

    def _resolve_redaction_target(
        self,
        *,
        page_index: int | None,
        page_label: PageSurfaceLabel | None,
    ) -> tuple[int, PageSurfaceLabel] | None: ...

    def _restore_document_scroll_position(
        self,
        *,
        horizontal_value: int,
        vertical_value: int,
    ) -> None: ...

    def _selected_bookmark_title(self) -> str | None: ...

    def _selected_page_surface_with_redaction(
        self,
    ) -> tuple[int, PageSurfaceLabel] | None: ...

    def _set_browse_mouse_mode(self) -> None: ...

    def _show_page_surface_context_menu(
        self,
        *,
        page_index: int,
        page_label: PageSurfaceLabel,
        position: QPoint,
    ) -> None: ...

    def _update_mouse_mode_indicator(self) -> None: ...


class BookmarkNavigationMixin(PageLinkNavigationMixin):
    """Populate, edit, and react to the bookmark navigation pane."""

    if TYPE_CHECKING:
        # Declared so the types match _BookmarkNavigationHost rather
        # than being inferred from the assignments below.
        _bookmark_item_by_page: dict[int, QTreeWidgetItem]
        _bookmark_pages_sorted: list[int]
        _active_page_surface_context_menu: QMenu | None

    def _handle_bookmark_selected(
        self: _BookmarkNavigationHost,
        item: QTreeWidgetItem,
        _column: int = 0,
    ) -> None:
        page_index = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(page_index, int):
            return

        self._document.go_to_page(page_index)
        self._sync_current_page_ui(scroll_to_page=True)

    def _populate_bookmarks(self: _BookmarkNavigationHost) -> None:
        self._bookmark_tree.clear()
        self._clear_bookmark_page_cache()
        self._bookmark_tree.setRootIsDecorated(False)
        if not self._document.has_document():
            return

        outline_items = self._document.outline_items()
        if not outline_items:
            placeholder = QTreeWidgetItem(["No bookmarks in this PDF"])
            placeholder.setFlags(
                placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable,
            )
            self._bookmark_tree.addTopLevelItem(placeholder)
            return

        self._bookmark_tree.setRootIsDecorated(
            any(item.level > 1 for item in outline_items),
        )
        parent_stack: dict[int, QTreeWidgetItem] = {}
        for outline_item in outline_items:
            tree_item = QTreeWidgetItem([outline_item.title])
            tree_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                outline_item.page_index,
            )
            tree_item.setData(
                0,
                Qt.ItemDataRole.UserRole + 1,
                outline_item.toc_index,
            )
            self._insert_bookmark_item(
                tree_item=tree_item,
                outline_item=outline_item,
                parent_stack=parent_stack,
            )

        self._bookmark_tree.expandToDepth(1)
        self._rebuild_bookmark_page_cache()

    def _insert_bookmark_item(
        self: _BookmarkNavigationHost,
        *,
        tree_item: QTreeWidgetItem,
        outline_item: PdfOutlineItem,
        parent_stack: dict[int, QTreeWidgetItem],
    ) -> None:
        parent_level = outline_item.level - 1
        while parent_level > 0 and parent_level not in parent_stack:
            parent_level -= 1

        if parent_level <= 0:
            self._bookmark_tree.addTopLevelItem(tree_item)
        else:
            parent_stack[parent_level].addChild(tree_item)

        parent_stack[outline_item.level] = tree_item
        levels_to_remove = [
            level for level in parent_stack if level > outline_item.level
        ]
        for level in levels_to_remove:
            del parent_stack[level]

    def _clear_bookmark_page_cache(self: _BookmarkNavigationHost) -> None:
        self._bookmark_item_by_page = {}
        self._bookmark_pages_sorted = []

    def _rebuild_bookmark_page_cache(self: _BookmarkNavigationHost) -> None:
        """Index bookmark items by destination page for O(log n) lookup.

        - Walks the tree breadth-first so the first item seen for a page
          wins, matching the original linear-scan tie-break.
        """
        item_by_page: dict[int, QTreeWidgetItem] = {}
        pending_items: list[QTreeWidgetItem] = []
        for top_level_index in range(self._bookmark_tree.topLevelItemCount()):
            top_level_item = self._bookmark_tree.topLevelItem(top_level_index)
            if top_level_item is not None:
                pending_items.append(top_level_item)

        while pending_items:
            item = pending_items.pop(0)
            item_page_index = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(item_page_index, int):
                item_by_page.setdefault(item_page_index, item)

            pending_items.extend(
                child_item
                for child_index in range(item.childCount())
                if (child_item := item.child(child_index)) is not None
            )

        self._bookmark_item_by_page = item_by_page
        self._bookmark_pages_sorted = sorted(item_by_page)

    def _find_bookmark_item_for_page(
        self: _BookmarkNavigationHost,
        page_index: int,
    ) -> QTreeWidgetItem | None:
        exact_match = self._bookmark_item_by_page.get(page_index)
        if exact_match is not None:
            return exact_match

        preceding_count = bisect_right(
            self._bookmark_pages_sorted,
            page_index,
        )
        if preceding_count == 0:
            return None

        nearest_page_index = self._bookmark_pages_sorted[preceding_count - 1]
        return self._bookmark_item_by_page[nearest_page_index]

    def _set_browse_mouse_mode(self: _BookmarkNavigationHost) -> None:
        self._is_pdf_edit_mode = False
        self._is_text_selection_mode = True
        self._apply_text_selection_mode()
        self._persist_pane_visibility_settings()

    def _set_text_selection_mouse_mode(self: _BookmarkNavigationHost) -> None:
        self._is_pdf_edit_mode = False
        self._is_text_selection_mode = True
        self._apply_text_selection_mode()
        self._persist_pane_visibility_settings()

    def _enter_pdf_edit_mode(self: _BookmarkNavigationHost) -> None:
        """Enter the text-selection mode used for content edits."""
        if not self._document.has_document():
            return

        self._is_pdf_edit_mode = True
        self._is_text_selection_mode = False
        self._apply_text_selection_mode()
        self.statusBar().showMessage(
            "Edit PDF mode: drag over text, then choose Replace Text "
            "or Remove Content.",
            5000,
        )

    def _toggle_mouse_mode(self: _BookmarkNavigationHost) -> None:
        self._set_browse_mouse_mode()

    def _apply_text_selection_mode(self: _BookmarkNavigationHost) -> None:
        if self._is_text_selection_mode:
            interaction_flags = (
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
        else:
            interaction_flags = Qt.TextInteractionFlag.NoTextInteraction
            text_cursor = self._page_text.textCursor()
            text_cursor.clearSelection()
            self._page_text.setTextCursor(text_cursor)

        self._page_text.setTextInteractionFlags(interaction_flags)
        for label_index, page_label in enumerate(self._page_labels):
            if not isinstance(page_label, PageSurfaceLabel):
                continue
            page_index = self._visible_page_indexes[label_index]
            page_label.set_text_selection_enabled(enabled=False)
            page_label.set_edit_selection_enabled(enabled=False)
            if self._is_pdf_edit_mode:
                page_label.set_edit_selection_enabled(enabled=True)
                continue

            page_label.set_text_selection_enabled(
                enabled=self._is_text_selection_mode,
            )
            if (
                self._is_text_selection_mode
                and page_index in self._rendered_page_indexes
            ):
                self._ensure_page_words_loaded(page_index)

        self._update_mouse_mode_indicator()

    def _update_mouse_mode_indicator(self: _BookmarkNavigationHost) -> None:
        mode_name = "Edit PDF" if self._is_pdf_edit_mode else "Read"
        self._mouse_mode_indicator.setText(f"Mode: {mode_name}")

    def _show_page_text_context_menu(
        self: _BookmarkNavigationHost,
        position: QPoint,
    ) -> None:
        menu = self._page_text.createStandardContextMenu()
        self._apply_context_menu_theme(menu, source_widget=self._page_text)
        bookmark_title = self._bookmark_title_from_text(
            self._page_text.textCursor().selectedText(),
        )
        bookmark_action = None
        if bookmark_title is not None:
            menu.addSeparator()
            bookmark_action = menu.addAction("Add Bookmark From Selection")

        selected_action = menu.exec(
            self._page_text.viewport().mapToGlobal(position),
        )
        if selected_action is bookmark_action and bookmark_title is not None:
            self._add_bookmark_from_selected_text(bookmark_title)

    def _show_bookmark_context_menu(
        self: _BookmarkNavigationHost,
        position: QPoint,
    ) -> None:
        item = self._bookmark_tree.itemAt(position)
        if item is None:
            return

        toc_index = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not isinstance(toc_index, int):
            return

        menu = QMenu(self._bookmark_tree)
        self._apply_context_menu_theme(menu, source_widget=self._bookmark_tree)
        rename_action = menu.addAction("Rename Bookmark")
        delete_action = menu.addAction("Delete Bookmark")

        selected_action = menu.exec(
            self._bookmark_tree.viewport().mapToGlobal(position),
        )
        if selected_action is rename_action:
            self._rename_bookmark_item(item, toc_index=toc_index)
            return

        if selected_action is delete_action:
            self._delete_bookmark_item(item, toc_index=toc_index)

    def _selected_bookmark_title(self: _BookmarkNavigationHost) -> str | None:
        if not self._is_text_selection_mode:
            return None

        return self._bookmark_title_from_text(
            self._page_text.textCursor().selectedText(),
        )

    def _apply_context_menu_theme(
        self: _BookmarkNavigationHost,
        menu: QMenu,
        *,
        source_widget: QWidget,
    ) -> None:
        palette = source_widget.window().palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        window_text_color = palette.color(QPalette.ColorRole.WindowText)
        highlight_color = palette.color(QPalette.ColorRole.Highlight)
        highlighted_text_color = palette.color(
            QPalette.ColorRole.HighlightedText,
        )
        border_color = palette.color(QPalette.ColorRole.Mid)
        disabled_text_color = palette.color(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.WindowText,
        )

        menu.setPalette(palette)
        menu.setStyleSheet(
            "\n".join(
                [
                    "QMenu {",
                    f"  background-color: {window_color.name()};",
                    f"  color: {window_text_color.name()};",
                    f"  border: 1px solid {border_color.name()};",
                    "  padding: 4px 0px;",
                    "}",
                    "QMenu::item {",
                    "  padding: 6px 24px 6px 12px;",
                    f"  color: {window_text_color.name()};",
                    "}",
                    "QMenu::item:selected {",
                    f"  background-color: {highlight_color.name()};",
                    f"  color: {highlighted_text_color.name()};",
                    "}",
                    "QMenu::item:disabled {",
                    f"  color: {disabled_text_color.name()};",
                    "}",
                    "QMenu::separator {",
                    "  height: 1px;",
                    f"  background: {border_color.name()};",
                    "  margin: 4px 8px;",
                    "}",
                ],
            ),
        )

    def _bookmark_title_from_text(
        self: _BookmarkNavigationHost,
        selected_text: str,
    ) -> str | None:
        normalized_text = " ".join(selected_text.split())
        if not normalized_text:
            return None

        if len(normalized_text) <= _BOOKMARK_TITLE_LIMIT:
            return normalized_text

        return f"{normalized_text[: _BOOKMARK_TITLE_LIMIT - 3].rstrip()}..."

    def _add_bookmark_from_selected_text(
        self: _BookmarkNavigationHost,
        title: str | None = None,
        *,
        page_index: int | None = None,
    ) -> None:
        bookmark_title = title or self._selected_bookmark_title()
        if bookmark_title is None:
            return

        try:
            self._document.add_bookmark(bookmark_title, page_index=page_index)
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to add bookmark:\n{error}")
            return

        self._populate_bookmarks()
        self._sync_current_page_ui(scroll_to_page=False)

    def _remove_selected_text(
        self: _BookmarkNavigationHost,
        *,
        page_index: int | None = None,
        page_label: PageSurfaceLabel | None = None,
    ) -> None:
        """Redact the current page-overlay word selection from the PDF."""
        if not self._document.has_document():
            return

        redaction_target = self._resolve_redaction_target(
            page_index=page_index,
            page_label=page_label,
        )
        if redaction_target is None:
            self._show_error(
                "Select a page region in Edit PDF mode, or select text first.",
            )
            return

        target_page_index, current_page_label = redaction_target
        selected_rectangles = current_page_label.selected_redaction_rectangles()
        if not selected_rectangles:
            self._show_error(
                "Select a page region in Edit PDF mode, or select text first.",
            )
            return

        horizontal_value = (
            self._document_scroll_area.horizontalScrollBar().value()
        )
        vertical_value = self._document_scroll_area.verticalScrollBar().value()

        try:
            changed = self._document.redact_text_rectangles(
                page_index=target_page_index,
                rectangles=selected_rectangles,
            )
        except PDF_IO_ERRORS as error:
            self._show_error(
                f"Failed to remove selected text:\n{error}",
            )
            return

        if not changed:
            self._show_error(
                "The selected text could not be removed.",
            )
            return

        if self._document.state.current_page_index != target_page_index:
            self._document.go_to_page(
                target_page_index,
                record_history=False,
            )

        self._clear_search_results()
        self._populate_thumbnails()
        self._refresh_document_view(scroll_to_page=False)
        QTimer.singleShot(
            0,
            lambda: self._restore_document_scroll_position(
                horizontal_value=horizontal_value,
                vertical_value=vertical_value,
            ),
        )
        self._refresh_actions()
        self.statusBar().showMessage("Removed content.", 5000)

    def _replace_selected_text(
        self: _BookmarkNavigationHost,
        *,
        page_index: int | None = None,
        page_label: PageSurfaceLabel | None = None,
    ) -> None:
        """Rewrite the text span the current page selection covers."""
        if not self._document.has_document():
            return

        target = self._resolve_redaction_target(
            page_index=page_index,
            page_label=page_label,
        )
        if target is None:
            self._show_error(
                "Select the text to replace in Edit PDF mode first.",
            )
            return

        target_page_index, current_page_label = target
        selected_rectangles = current_page_label.selected_redaction_rectangles()
        span = (
            self._document.span_for_rectangles(
                page_index=target_page_index,
                rectangles=selected_rectangles,
            )
            if selected_rectangles
            else None
        )
        if span is None:
            self._show_error(
                "No editable text was found in the selection.",
            )
            return

        replacement, accepted = QInputDialog.getText(
            cast("QWidget", self),
            "Replace Text",
            "Replacement text:",
            text=span.text,
        )
        if not accepted:
            return

        self._apply_text_span_replacement(span=span, replacement=replacement)

    def _apply_text_span_replacement(
        self: _BookmarkNavigationHost,
        *,
        span: PdfTextSpan,
        replacement: str,
    ) -> None:
        """Write one span replacement and refresh the affected views."""
        horizontal_value = (
            self._document_scroll_area.horizontalScrollBar().value()
        )
        vertical_value = self._document_scroll_area.verticalScrollBar().value()

        try:
            changed = self._document.replace_text_span(
                span=span,
                text=replacement,
            )
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to replace text:\n{error}")
            return

        if not changed:
            return

        if self._document.state.current_page_index != span.page_index:
            self._document.go_to_page(span.page_index, record_history=False)

        self._clear_search_results()
        self._populate_thumbnails()
        self._refresh_document_view(scroll_to_page=False)
        QTimer.singleShot(
            0,
            lambda: self._restore_document_scroll_position(
                horizontal_value=horizontal_value,
                vertical_value=vertical_value,
            ),
        )
        self._refresh_actions()
        self.statusBar().showMessage("Replaced text.", 5000)

    def _resolve_redaction_target(
        self: _BookmarkNavigationHost,
        *,
        page_index: int | None,
        page_label: PageSurfaceLabel | None,
    ) -> tuple[int, PageSurfaceLabel] | None:
        if page_index is None and page_label is None:
            selected_surface = self._selected_page_surface_with_redaction()
            if selected_surface is not None:
                return selected_surface

        target_page_index = (
            self._document.state.current_page_index
            if page_index is None
            else page_index
        )
        if page_label is not None:
            return target_page_index, page_label

        label_index = self._label_index_for_page(target_page_index)
        if label_index is None:
            return None

        candidate_label = self._page_labels[label_index]
        if not isinstance(candidate_label, PageSurfaceLabel):
            return None
        return target_page_index, candidate_label

    def _restore_document_scroll_position(
        self: _BookmarkNavigationHost,
        *,
        horizontal_value: int,
        vertical_value: int,
    ) -> None:
        """Restore the exact viewport scroll position after a rerender."""
        horizontal_bar = self._document_scroll_area.horizontalScrollBar()
        vertical_bar = self._document_scroll_area.verticalScrollBar()
        self._sync.scroll_position = True
        horizontal_bar.setValue(min(horizontal_value, horizontal_bar.maximum()))
        vertical_bar.setValue(min(vertical_value, vertical_bar.maximum()))
        self._sync.scroll_position = False
        self._document_scroll_area.viewport().update()
        self._refresh_visible_pages()

    def _selected_page_surface_with_redaction(
        self: _BookmarkNavigationHost,
    ) -> tuple[int, PageSurfaceLabel] | None:
        """Return the visible page surface that owns a redaction selection."""
        for label_index, candidate_label in enumerate(self._page_labels):
            if not isinstance(candidate_label, PageSurfaceLabel):
                continue
            if not candidate_label.selected_redaction_rectangles():
                continue
            return self._visible_page_indexes[label_index], candidate_label

        return None

    def _rename_bookmark_item(
        self: _BookmarkNavigationHost,
        item: QTreeWidgetItem,
        *,
        toc_index: int,
    ) -> None:
        current_title = item.text(0)
        updated_title = self._prompt_for_bookmark_title(current_title)
        if updated_title is None:
            return

        try:
            self._document.rename_bookmark(toc_index, updated_title)
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to rename bookmark:\n{error}")
            return

        self._populate_bookmarks()
        self._sync_current_page_ui(scroll_to_page=False)

    def _prompt_for_bookmark_title(
        self: _BookmarkNavigationHost,
        current_title: str,
    ) -> str | None:
        updated_title, accepted = QInputDialog.getText(
            self._bookmark_tree,
            "Rename Bookmark",
            "Bookmark title:",
            text=current_title,
        )
        if not accepted:
            return None

        return updated_title

    def _delete_bookmark_item(
        self: _BookmarkNavigationHost,
        item: QTreeWidgetItem,
        *,
        toc_index: int,
    ) -> None:
        bookmark_title = item.text(0)
        confirmation = QMessageBox.question(
            self._bookmark_tree,
            "Delete Bookmark",
            f"Delete bookmark '{bookmark_title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        try:
            self._document.delete_bookmark(toc_index)
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to delete bookmark:\n{error}")
            return

        self._populate_bookmarks()
        self._sync_current_page_ui(scroll_to_page=False)

    def _configure_page_surface(
        self: _BookmarkNavigationHost,
        page_label: PageSurfaceLabel,
        page_index: int,
    ) -> None:
        # Word boxes are loaded lazily (see _ensure_page_words_loaded) when
        # the page enters the render window, so opening/zooming a large PDF
        # does not extract text for every page up front.
        page_label.set_text_selection_enabled(
            enabled=self._is_text_selection_mode,
        )
        page_label.link_activated.connect(self._handle_page_link_activated)
        page_label.text_layer().customContextMenuRequested.connect(
            lambda position, current_page_index=page_index, current_label=page_label: (  # noqa: E501
                self._show_page_surface_context_menu(
                    page_index=current_page_index,
                    page_label=current_label,
                    position=position,
                )
            ),
        )

    def _ensure_page_words_loaded(
        self: _BookmarkNavigationHost,
        page_index: int,
    ) -> None:
        """Load text-overlay word boxes for one page on first need.

        - No-op outside text-selection mode or if already loaded for the
          current label generation (the set is cleared when labels rebuild,
          so a zoom change reloads at the new scale).
        """
        if not self._is_text_selection_mode:
            return
        if page_index in self._words_loaded_pages:
            return
        label_index = self._label_index_for_page(page_index)
        if label_index is None:
            return

        page_label = self._page_labels[label_index]
        if not isinstance(page_label, PageSurfaceLabel):
            return

        try:
            page_text_words = self._document.page_words(page_index)
        except PDF_IO_ERRORS:
            logger.exception(
                "Failed to load text overlay for page %d",
                page_index + 1,
            )
            # Mark handled so a deterministic extraction failure does not
            # re-raise on every re-render/scroll. The set is cleared when
            # labels rebuild (zoom/rotate/open), which retries then.
            self._words_loaded_pages.add(page_index)
            return

        page_label.set_page_text_words(
            page_text_words,
            zoom=self._document.state.zoom,
        )
        self._words_loaded_pages.add(page_index)

    def _show_page_surface_context_menu(
        self: _BookmarkNavigationHost,
        *,
        page_index: int,
        page_label: PageSurfaceLabel,
        position: QPoint,
    ) -> None:
        text_layer = page_label.text_layer()
        selected_text = page_label.selected_text()
        selected_rectangles = page_label.selected_redaction_rectangles()
        menu = text_layer.createStandardContextMenu()
        self._apply_context_menu_theme(menu, source_widget=text_layer)

        bookmark_title = self._bookmark_title_from_text(selected_text)
        if bookmark_title is not None:
            menu.addSeparator()
            bookmark_action = menu.addAction("Add Bookmark From Selection")
            bookmark_action.triggered.connect(
                partial(
                    self._add_bookmark_from_selected_text,
                    bookmark_title,
                    page_index=page_index,
                ),
            )

        if selected_rectangles:
            if bookmark_title is None:
                menu.addSeparator()
            replace_text_action = menu.addAction("Replace Text...")
            replace_text_action.triggered.connect(
                partial(
                    self._replace_selected_text,
                    page_index=page_index,
                    page_label=page_label,
                ),
            )
            remove_text_action = menu.addAction("Remove Content")
            remove_text_action.triggered.connect(
                partial(
                    self._remove_selected_text,
                    page_index=page_index,
                    page_label=page_label,
                ),
            )

        menu.aboutToHide.connect(menu.deleteLater)
        self._active_page_surface_context_menu = menu
        menu.aboutToHide.connect(
            lambda: setattr(
                self,
                "_active_page_surface_context_menu",
                None,
            ),
        )
        menu.popup(text_layer.viewport().mapToGlobal(position))
