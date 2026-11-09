"""Application entry point for the desktop PDF viewer."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from open_pdf.adapters.ocr.tesseract import (
    create_tesseract_ocr_backend,
    tesseract_setup_message,
)
from open_pdf.adapters.runtime.desktop_session import instance_server_name
from open_pdf.adapters.runtime.single_instance import SingleInstanceCoordinator
from open_pdf.application.startup import prepare_storage
from open_pdf.config.crash_reporting import install_crash_handlers
from open_pdf.config.path_handler import ASSETS_DIR
from open_pdf.gui.views.dialogs.crash_dialog import QtCrashNotifier

if TYPE_CHECKING:
    from collections.abc import Sequence

    from open_pdf.adapters.ocr.backend import PdfOcrBackend

logger = logging.getLogger(__name__)


_APP_NAME = "Open PDF"
_APP_ICON_PATH = ASSETS_DIR / "open_pdf.png"
_APP_FONT_DIRECTORY = ASSETS_DIR / "fonts"


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the desktop viewer.

    Returns:
        The parser that accepts an optional PDF path to open at launch.

    """
    parser = argparse.ArgumentParser(description="Open PDF desktop viewer")
    parser.add_argument(
        "pdf_path",
        nargs="?",
        type=Path,
        help="Optional PDF to open on launch.",
    )
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    return parser


def _configure_qt_font_directory() -> None:
    """Point Qt at bundled fonts when the directory exists."""
    if _APP_FONT_DIRECTORY.exists():
        os.environ.setdefault("QT_QPA_FONTDIR", str(_APP_FONT_DIRECTORY))


def _create_default_ocr_backend() -> PdfOcrBackend | None:
    """Return the preferred OCR backend for this process, if any."""
    return create_tesseract_ocr_backend()


def _default_ocr_unavailable_message() -> str | None:
    """Return startup guidance for OCR when the preferred backend is absent."""
    return tesseract_setup_message()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the desktop PDF viewer application.

    Returns:
        The Qt application exit code.

    """
    parser = build_argument_parser()
    arguments = parser.parse_args(argv)
    if arguments.smoke_test and arguments.pdf_path is None:
        parser.error("--smoke-test requires a PDF path")

    prepare_storage()
    # Import storage consumers after preparing the XDG directories.
    from open_pdf.config.logging.log_config import (  # noqa: PLC0415
        application_log_path,
        configure_logging,
    )
    from open_pdf.gui.app import MainWindow  # noqa: PLC0415

    configure_logging(_APP_NAME)
    log_path = application_log_path(_APP_NAME)
    install_crash_handlers(log_path=log_path)
    _configure_qt_font_directory()

    application = QApplication(list(argv) if argv is not None else sys.argv)
    application.setApplicationName(_APP_NAME)
    application.setDesktopFileName("com.plaintxtoffice.OpenPDF")
    if not arguments.smoke_test:
        install_crash_handlers(
            notify=QtCrashNotifier(application).notify,
            log_path=log_path,
        )
    if _APP_ICON_PATH.exists():
        application.setWindowIcon(QIcon(str(_APP_ICON_PATH)))

    single_instance = None
    if not arguments.smoke_test:
        single_instance = SingleInstanceCoordinator(instance_server_name())
        if single_instance.notify_existing_instance(arguments.pdf_path):
            return 0

    window = MainWindow(
        initial_path=arguments.pdf_path,
        ocr_backend=_create_default_ocr_backend(),
        ocr_unavailable_message=_default_ocr_unavailable_message(),
    )
    if single_instance is not None:
        single_instance.start_listening(window)
        application.aboutToQuit.connect(single_instance.close)
    window.show()
    if arguments.smoke_test:
        from open_pdf.gui.views.workflows.smoke import schedule_smoke_check

        schedule_smoke_check(application, window)
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
