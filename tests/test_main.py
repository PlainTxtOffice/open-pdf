# ruff: noqa: E402

import os
import sys

from pathlib import Path
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_FONT_DIRECTORY = Path(__file__).resolve().parents[1] / "assets" / "fonts"
if _FONT_DIRECTORY.exists():
    os.environ.setdefault("QT_QPA_FONTDIR", str(_FONT_DIRECTORY))

from PySide6.QtWidgets import QApplication

import src.main as main_module
from src.adapters.runtime.single_instance import SingleInstanceCoordinator


class _FakeWindow:
    def __init__(self) -> None:
        self.present_calls = 0
        self.opened_paths: list[Path] = []

    def present(self) -> None:
        self.present_calls += 1

    def open_document_in_tab(self, path: Path) -> None:
        self.opened_paths.append(path)


def _app() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


def _pump_events() -> None:
    application = _app()
    for _ in range(3):
        application.processEvents()


def test_single_instance_coordinator_forwards_pdf_path(
    tmp_path: Path,
) -> None:
    _app()
    coordinator = SingleInstanceCoordinator(
        f"openpdf-test-{uuid4()}",
    )
    window = _FakeWindow()

    try:
        coordinator.start_listening(window)
        pdf_path = tmp_path / "forwarded.pdf"

        assert coordinator.notify_existing_instance(pdf_path) is True

        _pump_events()

        assert window.present_calls == 1
        assert window.opened_paths == [pdf_path]
    finally:
        coordinator.close()


def test_single_instance_coordinator_activates_existing_window_without_path() -> (
    None
):
    _app()
    coordinator = SingleInstanceCoordinator(
        f"openpdf-test-{uuid4()}",
    )
    window = _FakeWindow()

    try:
        coordinator.start_listening(window)

        assert coordinator.notify_existing_instance(None) is True

        _pump_events()

        assert window.present_calls == 1
        assert window.opened_paths == []
    finally:
        coordinator.close()


def test_single_instance_coordinator_returns_false_without_primary_instance() -> (
    None
):
    _app()
    coordinator = SingleInstanceCoordinator(
        f"openpdf-test-{uuid4()}",
    )

    try:
        assert coordinator.notify_existing_instance(None) is False
    finally:
        coordinator.close()


def test_create_default_ocr_backend_uses_tesseract_factory(
    monkeypatch,
) -> None:
    backend_marker = object()

    monkeypatch.setattr(
        main_module,
        "create_tesseract_ocr_backend",
        lambda: backend_marker,
    )

    assert main_module._create_default_ocr_backend() is backend_marker


def test_default_ocr_unavailable_message_uses_tesseract_helper(
    monkeypatch,
) -> None:
    guidance = "Install Tesseract first"

    monkeypatch.setattr(
        main_module,
        "tesseract_setup_message",
        lambda: guidance,
    )

    assert main_module._default_ocr_unavailable_message() == guidance
