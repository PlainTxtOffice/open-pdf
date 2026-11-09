"""Pane visibility behavior for the PySide6 PDF window."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import (
        QListWidget,
        QSplitter,
        QTextEdit,
        QTreeWidget,
        QWidget,
    )


class _ViewPaneHost(Protocol):
    """Describe the main-window API required to toggle secondary panes."""

    _bookmark_tree: QTreeWidget
    _thumbnail_list: QListWidget
    _thumbnail_pane: QWidget
    _page_text: QTextEdit
    _notes_text: QTextEdit
    _main_splitter: QSplitter
    _bookmarks_pane_action: QAction
    _thumbnails_pane_action: QAction
    _text_pane_action: QAction
    _notes_pane_action: QAction
    _bookmarks_left_side_action: QAction
    _thumbnails_left_side_action: QAction
    _thumbnails_on_left: bool

    def _persist_pane_visibility_settings(self) -> None: ...

    def _apply_side_pane_layout(self) -> None: ...


class ViewPaneMixin:
    """Toggle secondary panes from View menu actions."""

    def _set_bookmarks_pane_visible(
        self: _ViewPaneHost,
        *,
        is_visible: bool,
    ) -> None:
        self._bookmark_tree.setVisible(is_visible)
        self._persist_pane_visibility_settings()

    def _set_thumbnails_pane_visible(
        self: _ViewPaneHost,
        *,
        is_visible: bool,
    ) -> None:
        self._thumbnail_pane.setVisible(is_visible)
        self._persist_pane_visibility_settings()

    def _set_text_pane_visible(
        self: _ViewPaneHost,
        *,
        is_visible: bool,
    ) -> None:
        self._page_text.setVisible(is_visible)
        self._persist_pane_visibility_settings()

    def _set_notes_pane_visible(
        self: _ViewPaneHost,
        *,
        is_visible: bool,
    ) -> None:
        self._notes_text.setVisible(is_visible)
        self._persist_pane_visibility_settings()

    def _place_bookmarks_on_left(self: _ViewPaneHost) -> None:
        self._thumbnails_on_left = False
        self._apply_side_pane_layout()
        self._persist_pane_visibility_settings()

    def _place_thumbnails_on_left(self: _ViewPaneHost) -> None:
        self._thumbnails_on_left = True
        self._apply_side_pane_layout()
        self._persist_pane_visibility_settings()

    def _apply_side_pane_layout(self: _ViewPaneHost) -> None:
        left_widget = (
            self._thumbnail_pane
            if self._thumbnails_on_left
            else self._bookmark_tree
        )
        right_widget = (
            self._bookmark_tree
            if self._thumbnails_on_left
            else self._thumbnail_pane
        )
        self._main_splitter.insertWidget(0, left_widget)
        self._main_splitter.insertWidget(2, right_widget)
