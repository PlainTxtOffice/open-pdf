"""Edit menu helpers for the PySide6 PDF window."""

# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtGui import QAction

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QMenu

    from open_pdf.gui.views.menus.menu_window_protocol import MenuWindow


def populate_edit_menu(edit_menu: QMenu, window: MenuWindow) -> None:
    """Populate the Edit menu actions."""
    add_ocr_actions(window)
    add_page_actions(window)
    edit_menu.addAction(window._run_ocr_page_action)
    edit_menu.addAction(window._run_ocr_document_action)
    edit_menu.addSeparator()
    edit_menu.addAction(window._insert_page_before_action)
    edit_menu.addAction(window._insert_page_after_action)
    edit_menu.addSeparator()
    edit_menu.addAction(window._remove_selected_text_action)


def add_page_actions(window: MenuWindow) -> None:
    """Create the page-insertion actions owned by the Edit menu."""
    action_parent = cast("QObject", window)

    window._insert_page_before_action = QAction(
        "Insert Blank Page Before",
        action_parent,
    )
    window._insert_page_before_action.triggered.connect(
        window._insert_blank_page_before,
    )

    window._insert_page_after_action = QAction(
        "Insert Blank Page After",
        action_parent,
    )
    window._insert_page_after_action.triggered.connect(
        window._insert_blank_page_after,
    )


def add_ocr_actions(window: MenuWindow) -> None:
    """Create the OCR actions owned by the Edit menu."""
    action_parent = cast("QObject", window)

    window._run_ocr_page_action = QAction(
        "Run OCR on Current Page",
        action_parent,
    )
    window._run_ocr_page_action.triggered.connect(
        window._run_ocr_for_current_page,
    )

    window._run_ocr_document_action = QAction(
        "Run OCR on Document",
        action_parent,
    )
    window._run_ocr_document_action.triggered.connect(
        window._run_ocr_for_document,
    )
