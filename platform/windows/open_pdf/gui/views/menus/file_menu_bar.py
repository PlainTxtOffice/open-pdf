"""Menu bar construction for the PySide6 PDF window."""

from __future__ import annotations

from typing import TYPE_CHECKING

from open_pdf.gui.views.menus.edit_menu import populate_edit_menu
from open_pdf.gui.views.menus.file_menu import populate_file_menu
from open_pdf.gui.views.menus.help.help_menu import populate_help_menu
from open_pdf.gui.views.menus.view_menu import populate_view_menu

if TYPE_CHECKING:
    from open_pdf.gui.views.menus.menu_window_protocol import MenuWindow


def build_menu_bar(window: MenuWindow) -> None:
    """Build the top-level menu bar for the main window."""
    menu_bar = window.menuBar()
    menu_bar.clear()

    file_menu = menu_bar.addMenu("File")
    populate_file_menu(file_menu, window)

    edit_menu = menu_bar.addMenu("Edit")
    populate_edit_menu(edit_menu, window)

    view_menu = menu_bar.addMenu("View")
    populate_view_menu(view_menu, window)

    help_menu = menu_bar.addMenu("Help")
    populate_help_menu(help_menu, window)
