"""Receive Finder document-open events before and after window creation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent
from PySide6.QtGui import QFileOpenEvent
from PySide6.QtWidgets import QApplication

from open_pdf.adapters.runtime.single_instance import InstanceWindow


class MacApplication(QApplication):
    """Queue early Finder requests until the document window is ready."""

    def __init__(self, arguments: list[str]) -> None:
        self._window: InstanceWindow | None = None
        self._pending: list[Path] = []
        super().__init__(arguments)

    def attach_window(self, window: InstanceWindow) -> None:
        """Deliver all startup requests in their original order."""
        self._window = window
        pending, self._pending = self._pending, []
        for path in pending:
            self.open_file(path)

    def open_file(self, path: Path) -> None:
        """Open a local document in the existing tabbed window."""
        path = path.expanduser().resolve()
        if self._window is None:
            self._pending.append(path)
        else:
            self._window.present()
            self._window.open_document_in_tab(path)

    def event(self, event: QEvent) -> bool:
        """Handle local files delivered by Launch Services and Dock drops."""
        if isinstance(event, QFileOpenEvent):
            path = event.file()
            if not path and event.url().isLocalFile():
                path = event.url().toLocalFile()
            if path:
                self.open_file(Path(path))
                event.accept()
                return True
            return False
        return super().event(event)
