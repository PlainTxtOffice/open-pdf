"""About dialog helper for Open PDF."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def show_about_open_pdf_dialog(parent: QWidget) -> None:
    """Show the About Open PDF dialog."""
    QMessageBox.about(
        parent,
        "About Open PDF",
        "Open PDF\n\nA lightweight desktop PDF viewer and editor.",
    )
