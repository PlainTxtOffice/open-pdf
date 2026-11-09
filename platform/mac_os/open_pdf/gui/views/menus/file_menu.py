"""File menu helpers for the PySide6 PDF window."""

# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtGui import QAction, QKeySequence

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QMenu

    from open_pdf.gui.views.menus.menu_window_protocol import MenuWindow


def populate_file_menu(file_menu: QMenu, window: MenuWindow) -> None:
    """Populate the File menu actions."""
    add_file_menu_actions(window)

    file_menu.addAction(window._open_action)
    file_menu.addAction(window._save_action)
    file_menu.addAction(window._save_as_action)
    file_menu.addSeparator()
    file_menu.addAction(window._rename_file_action)
    file_menu.addAction(window._print_action)
    file_menu.addAction(window._properties_action)
    file_menu.addAction(window._close_tab_action)
    file_menu.addSeparator()
    file_menu.addAction(window._exit_action)


def add_file_menu_actions(window: MenuWindow) -> None:
    """Create menu-only File actions."""
    action_parent = cast("QObject", window)

    window._close_tab_action = QAction("Close Tab", action_parent)
    window._close_tab_action.setShortcut(QKeySequence.StandardKey.Close)
    window._close_tab_action.triggered.connect(
        window._close_current_tab,
    )

    window._properties_action = QAction("Properties", action_parent)
    window._properties_action.triggered.connect(
        window._edit_document_properties,
    )

    window._rename_file_action = QAction("Rename File", action_parent)
    window._rename_file_action.triggered.connect(
        window._rename_file,
    )

    window._print_action = QAction("Print", action_parent)
    window._print_action.setShortcut(QKeySequence.StandardKey.Print)
    window._print_action.triggered.connect(
        window._print_document,
    )

    window._exit_action = QAction("Quit Open PDF", action_parent)
    window._exit_action.setMenuRole(QAction.MenuRole.QuitRole)
    window._exit_action.setShortcut(QKeySequence.StandardKey.Quit)
    window._exit_action.triggered.connect(window.close)
