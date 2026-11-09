"""View menu helpers for the PySide6 PDF window."""

# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtGui import QAction, QActionGroup

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QMenu

    from open_pdf.gui.views.menus.menu_window_protocol import MenuWindow


def populate_view_menu(view_menu: QMenu, window: MenuWindow) -> None:
    """Populate the View menu actions."""
    view_menu.addAction(window._actual_size_action)
    view_menu.addAction(window._fit_width_action)
    view_menu.addAction(window._fit_page_action)
    view_menu.addAction(window._single_page_view_action)
    view_menu.addSeparator()
    add_mouse_mode_actions(window)
    view_menu.addAction(window._browse_mouse_mode_action)
    view_menu.addSeparator()
    add_pane_actions(window)
    view_menu.addAction(window._bookmarks_pane_action)
    view_menu.addAction(window._thumbnails_pane_action)
    view_menu.addAction(window._text_pane_action)
    view_menu.addAction(window._notes_pane_action)
    view_menu.addSeparator()
    add_side_pane_actions(window)
    view_menu.addAction(window._bookmarks_left_side_action)
    view_menu.addAction(window._thumbnails_left_side_action)


def add_mouse_mode_actions(window: MenuWindow) -> None:
    """Create mutually exclusive mouse mode actions for extracted text pane."""
    action_parent = cast("QObject", window)

    mouse_mode_group = QActionGroup(action_parent)
    mouse_mode_group.setExclusive(True)

    window._browse_mouse_mode_action = QAction(
        "Read Mode",
        action_parent,
    )
    window._browse_mouse_mode_action.setCheckable(True)
    window._browse_mouse_mode_action.setChecked(True)
    window._browse_mouse_mode_action.triggered.connect(
        window._set_browse_mouse_mode,
    )
    mouse_mode_group.addAction(window._browse_mouse_mode_action)

    window._text_selection_mouse_mode_action = QAction(
        "Read Mode",
        action_parent,
    )
    window._text_selection_mouse_mode_action.setCheckable(True)
    window._text_selection_mouse_mode_action.triggered.connect(
        window._set_text_selection_mouse_mode,
    )
    mouse_mode_group.addAction(
        window._text_selection_mouse_mode_action,
    )


def add_pane_actions(window: MenuWindow) -> None:
    """Create checkable pane visibility actions for the View menu."""
    action_parent = cast("QObject", window)

    window._bookmarks_pane_action = QAction("Bookmarks", action_parent)
    window._bookmarks_pane_action.setCheckable(True)
    window._bookmarks_pane_action.setChecked(True)
    window._bookmarks_pane_action.toggled.connect(
        lambda is_visible: window._set_bookmarks_pane_visible(
            is_visible=is_visible,
        ),
    )

    window._thumbnails_pane_action = QAction(
        "Thumbnails",
        action_parent,
    )
    window._thumbnails_pane_action.setCheckable(True)
    window._thumbnails_pane_action.setChecked(True)
    window._thumbnails_pane_action.toggled.connect(
        lambda is_visible: window._set_thumbnails_pane_visible(
            is_visible=is_visible,
        ),
    )

    window._text_pane_action = QAction("Extracted Text", action_parent)
    window._text_pane_action.setCheckable(True)
    window._text_pane_action.setChecked(True)
    window._text_pane_action.toggled.connect(
        lambda is_visible: window._set_text_pane_visible(
            is_visible=is_visible,
        ),
    )

    window._notes_pane_action = QAction("Notes", action_parent)
    window._notes_pane_action.setCheckable(True)
    window._notes_pane_action.setChecked(True)
    window._notes_pane_action.toggled.connect(
        lambda is_visible: window._set_notes_pane_visible(
            is_visible=is_visible,
        ),
    )


def add_side_pane_actions(window: MenuWindow) -> None:
    """Create mutually exclusive actions that choose which side pane is left."""
    action_parent = cast("QObject", window)

    side_pane_group = QActionGroup(action_parent)
    side_pane_group.setExclusive(True)

    window._bookmarks_left_side_action = QAction(
        "Bookmarks On Left",
        action_parent,
    )
    window._bookmarks_left_side_action.setCheckable(True)
    window._bookmarks_left_side_action.setChecked(True)
    window._bookmarks_left_side_action.triggered.connect(
        window._place_bookmarks_on_left,
    )
    side_pane_group.addAction(window._bookmarks_left_side_action)

    window._thumbnails_left_side_action = QAction(
        "Thumbnails On Left",
        action_parent,
    )
    window._thumbnails_left_side_action.setCheckable(True)
    window._thumbnails_left_side_action.triggered.connect(
        window._place_thumbnails_on_left,
    )
    side_pane_group.addAction(window._thumbnails_left_side_action)
