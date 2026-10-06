"""Application entry point for the desktop PDF viewer."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.adapters.ocr.tesseract import (
    create_tesseract_ocr_backend,
    tesseract_setup_message,
)
from src.adapters.runtime.single_instance import SingleInstanceCoordinator
from src.config.crash_reporting import install_crash_handlers
from src.config.logging.log_config import (
    application_log_path,
    configure_logging,
)
from src.config.path_handler import ROOT_DIR
from src.gui.app import MainWindow
from src.gui.views.dialogs.crash_dialog import QtCrashNotifier

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.domains.document.models import PdfOcrBackend

logger = logging.getLogger(__name__)


_APP_NAME = "Open PDF"
_APP_USER_MODEL_ID = "openpdf.viewer.0"
_APP_ASSETS_DIRECTORY = ROOT_DIR / "assets"
_APP_ICON_PATH = _APP_ASSETS_DIRECTORY / "app.ico"
_APP_FONT_DIRECTORY = _APP_ASSETS_DIRECTORY / "fonts"
_SINGLE_INSTANCE_SERVER_NAME = "openpdf.viewer.primary"


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
    return parser


def _claim_windows_taskbar_identity() -> None:
    """Tag the process so the Windows taskbar uses our icon, not Python's."""
    if sys.platform != "win32":
        return

    with contextlib.suppress(AttributeError, OSError):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            _APP_USER_MODEL_ID,
        )


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

    configure_logging(_APP_NAME)
    log_path = application_log_path(_APP_NAME)
    install_crash_handlers(log_path=log_path)
    _claim_windows_taskbar_identity()
    _configure_qt_font_directory()

    application = QApplication(list(argv) if argv is not None else sys.argv)
    application.setApplicationName(_APP_NAME)
    install_crash_handlers(
        notify=QtCrashNotifier(application).notify,
        log_path=log_path,
    )
    if _APP_ICON_PATH.exists():
        application.setWindowIcon(QIcon(str(_APP_ICON_PATH)))

    single_instance = SingleInstanceCoordinator(_SINGLE_INSTANCE_SERVER_NAME)
    if single_instance.notify_existing_instance(arguments.pdf_path):
        return 0

    window = MainWindow(
        initial_path=arguments.pdf_path,
        ocr_backend=_create_default_ocr_backend(),
        ocr_unavailable_message=_default_ocr_unavailable_message(),
    )
    single_instance.start_listening(window)
    application.aboutToQuit.connect(single_instance.close)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
