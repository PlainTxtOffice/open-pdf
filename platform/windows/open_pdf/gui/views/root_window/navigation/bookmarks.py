"""Bookmark navigation behavior for the PySide6 PDF window."""

from __future__ import annotations

import logging
from bisect import bisect_right
from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QInputDialog,
    QMenu,
    QMessageBox,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from open_pdf.adapters.document.errors import PDF_IO_ERRORS
from open_pdf.gui.views.root_window.navigation.page_links import (
    PageLinkNavigationMixin,
)

if TYPE_CHECKING:
    from open_pdf.application.document.session import PdfDocument
    from open_pdf.domains.document.models import (
        PdfOutlineItem,
    )


logger = logging.getLogger(__name__)

_BOOKMARK_TITLE_LIMIT = 80


class _BookmarkNavigationHost(Protocol):
    """Describe the window operations required by this workflow."""

    _document: PdfDocument

    _bookmark_tree: QTreeWidget

    _page_text: QTextEdit

    _is_text_selection_mode: bool

    _bookmark_item_by_page: dict[int, QTreeWidgetItem]

    _bookmark_pages_sorted: list[int]

    def _sync_current_page_ui(
        self,
        *,
        scroll_to_page: bool,
    ) -> None: ...

    def _show_error(self, message: str) -> None: ...

    def _apply_context_menu_theme(
        self,
        menu: QMenu,
        *,
        source_widget: QWidget,
    ) -> None: ...

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

    def _rename_bookmark_item(
        self,
        item: QTreeWidgetItem,
        *,
        toc_index: int,
    ) -> None: ...

    def _selected_bookmark_title(self) -> str | None: ...


class BookmarkNavigationMixin(PageLinkNavigationMixin):
    """Populate, edit, and react to the bookmark navigation pane."""

    if TYPE_CHECKING:
        # Declared so the types match _BookmarkNavigationHost rather
        # than being inferred from the assignments below.
        _bookmark_item_by_page: dict[int, QTreeWidgetItem]
        _bookmark_pages_sorted: list[int]

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
