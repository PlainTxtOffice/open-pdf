"""Shared protocol for menu-building helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMenuBar, QTextEdit


class MenuWindow(Protocol):
    """Describe the host window state required by menu helpers."""

    _open_action: QAction
    _save_action: QAction
    _save_as_action: QAction
    _run_ocr_page_action: QAction
    _run_ocr_document_action: QAction
    _rename_file_action: QAction
    _print_action: QAction
    _properties_action: QAction
    _close_tab_action: QAction
    _exit_action: QAction
    _actual_size_action: QAction
    _fit_width_action: QAction
    _fit_page_action: QAction
    _single_page_view_action: QAction
    _edit_pdf_action: QAction
    _remove_selected_text_action: QAction
    _insert_page_before_action: QAction
    _insert_page_after_action: QAction
    _rotate_right_action: QAction
    _bookmarks_pane_action: QAction
    _thumbnails_pane_action: QAction
    _text_pane_action: QAction
    _notes_pane_action: QAction
    _bookmarks_left_side_action: QAction
    _thumbnails_left_side_action: QAction
    _browse_mouse_mode_action: QAction
    _text_selection_mouse_mode_action: QAction
    _about_action: QAction
    _page_text: QTextEdit
    _notes_text: QTextEdit

    def menuBar(self) -> QMenuBar:  # noqa: N802
        """Return the main window menu bar."""
        ...

    def close(self) -> bool:
        """Request that the window close."""
        ...

    def _print_document(self) -> None: ...

    def _insert_blank_page_before(self) -> None: ...

    def _insert_blank_page_after(self) -> None: ...

    def _close_current_tab(self) -> None: ...

    def _edit_document_properties(self) -> None: ...

    def _rename_file(self) -> None: ...

    def _run_ocr_for_current_page(self) -> None: ...

    def _run_ocr_for_document(self) -> None: ...

    def _set_bookmarks_pane_visible(
        self,
        *,
        is_visible: bool,
    ) -> None: ...

    def _set_thumbnails_pane_visible(
        self,
        *,
        is_visible: bool,
    ) -> None: ...

    def _set_text_pane_visible(
        self,
        *,
        is_visible: bool,
    ) -> None: ...

    def _set_notes_pane_visible(
        self,
        *,
        is_visible: bool,
    ) -> None: ...

    def _place_bookmarks_on_left(self) -> None: ...

    def _place_thumbnails_on_left(self) -> None: ...

    def _set_browse_mouse_mode(self) -> None: ...

    def _set_text_selection_mouse_mode(self) -> None: ...

    def _enter_pdf_edit_mode(self) -> None: ...

    def _remove_selected_text(self) -> None: ...

    def _show_about_dialog(self) -> None: ...
