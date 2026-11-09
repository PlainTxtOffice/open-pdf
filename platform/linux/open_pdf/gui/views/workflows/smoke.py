"""Exercise real PDF rendering inside the packaged Qt application."""

from time import monotonic

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from open_pdf.gui.views.root_window.window import MainWindow


def schedule_smoke_check(application: QApplication, window: MainWindow) -> None:
    """Exit successfully only after a page is rendered in a visible window."""
    deadline = monotonic() + 15
    timer = QTimer(window)

    def check() -> None:
        rendered = (
            window.isVisible()
            and window._document.has_document()
            and 0 in window._rendered_page_indexes
            and not application.windowIcon().isNull()
            and not window.grab().isNull()
        )
        if not rendered and monotonic() < deadline:
            return
        timer.stop()
        window._thread_pool.waitForDone(5000)
        print("OPEN_PDF_SMOKE_OK" if rendered else "OPEN_PDF_SMOKE_FAILED",
              flush=True)
        window.close()
        application.exit(0 if rendered else 1)

    timer.timeout.connect(check)
    timer.start(100)
