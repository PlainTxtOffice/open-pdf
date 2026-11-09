"""macOS application entry point."""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtGui import QIcon

from open_pdf.adapters.ocr.tesseract import (
    create_tesseract_ocr_backend,
    tesseract_setup_message,
)
from open_pdf.adapters.runtime.single_instance import SingleInstanceCoordinator
from open_pdf.application.startup import prepare_storage
from open_pdf.config.crash_reporting import install_crash_handlers
from open_pdf.config.path_handler import ASSETS_DIR
from open_pdf.gui.application import MacApplication
from open_pdf.gui.views.dialogs.crash_dialog import QtCrashNotifier


def build_argument_parser() -> argparse.ArgumentParser:
    """Accept one or several documents from a shell launch."""
    parser = argparse.ArgumentParser(description="Open PDF for macOS")
    parser.add_argument("pdf_paths", nargs="*", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Initialize native storage and run the document window."""
    arguments = build_argument_parser().parse_args(argv)
    prepare_storage()
    from open_pdf.config.logging.log_config import (
        application_log_path,
        configure_logging,
    )
    from open_pdf.gui.app import MainWindow

    configure_logging("Open PDF")
    application = MacApplication([sys.argv[0]])
    application.setApplicationName("Open PDF")
    application.setWindowIcon(QIcon(str(ASSETS_DIR / "open_pdf.png")))
    install_crash_handlers(
        notify=QtCrashNotifier(application).notify,
        log_path=application_log_path("Open PDF"),
    )
    user_key = hashlib.sha256(str(Path.home()).encode()).hexdigest()[:16]
    coordinator = SingleInstanceCoordinator(f"open-pdf-macos-{user_key}")
    paths = [path.expanduser().resolve() for path in arguments.pdf_paths]
    if coordinator.notify_existing_instance(paths[0] if paths else None):
        for path in paths[1:]:
            coordinator.notify_existing_instance(path)
        return 0
    window = MainWindow(
        ocr_backend=create_tesseract_ocr_backend(),
        ocr_unavailable_message=tesseract_setup_message(),
    )
    coordinator.start_listening(window)
    application.aboutToQuit.connect(coordinator.close)
    application.attach_window(window)
    for path in paths:
        application.open_file(path)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
