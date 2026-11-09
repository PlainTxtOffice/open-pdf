"""Qt presentation for unhandled-exception crash reports."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QMessageBox

CRASH_DIALOG_TITLE = "Open PDF"


class QtCrashNotifier(QObject):
    """Show crash reports in a dialog on the GUI thread.

    - Reports arrive from whichever thread raised, including Qt thread-pool
      workers, so every message is delivered over a queued connection.
    - The queued delivery also lets the failing slot unwind before a modal
      dialog spins a nested event loop.
    - Repeat reports are dropped while a dialog is open so a failing render
      loop cannot bury the window in dialogs.
    """

    _reported = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        """Wire the queued delivery of crash messages to the dialog."""
        super().__init__(parent)
        self._dialog_open = False
        self._reported.connect(
            self._show_dialog,
            Qt.ConnectionType.QueuedConnection,
        )

    def notify(self, message: str) -> None:
        """Queue one crash message for display on the GUI thread."""
        self._reported.emit(message)

    def _show_dialog(self, message: str) -> None:
        """Show one crash message unless a crash dialog is already open."""
        if self._dialog_open:
            return

        self._dialog_open = True
        try:
            QMessageBox.critical(None, CRASH_DIALOG_TITLE, message)
        finally:
            self._dialog_open = False
