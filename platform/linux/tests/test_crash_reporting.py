# ruff: noqa: E402

import logging
import os
import sys
import threading

from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

import open_pdf.config.crash_reporting as crash_reporting

from open_pdf.config.crash_reporting import (
    crash_message,
    install_crash_handlers,
)
from open_pdf.gui.views.dialogs.crash_dialog import QtCrashNotifier


@pytest.fixture(autouse=True)
def _restore_hooks():
    original_excepthook = sys.excepthook
    original_thread_excepthook = threading.excepthook
    original_installed = crash_reporting._installed
    original_notify = crash_reporting._notify
    original_log_path = crash_reporting._log_path
    crash_reporting._installed = False
    try:
        yield
    finally:
        sys.excepthook = original_excepthook
        threading.excepthook = original_thread_excepthook
        crash_reporting._installed = original_installed
        crash_reporting._notify = original_notify
        crash_reporting._log_path = original_log_path
        crash_reporting._reporting = False


def _raised(error: BaseException) -> BaseException:
    """Return the error with a real traceback attached."""
    try:
        raise error
    except BaseException as raised_error:  # noqa: BLE001
        return raised_error


def _app() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


def test_crash_notifier_alias_resolves() -> None:
    assert crash_reporting.CrashNotifier.__value__ is not None


def test_install_crash_handlers_replaces_interpreter_hooks() -> None:
    install_crash_handlers()

    assert sys.excepthook is crash_reporting._handle_exception
    assert threading.excepthook is crash_reporting._handle_thread_exception


def test_unhandled_exception_is_logged_and_reported(caplog) -> None:
    messages: list[str] = []
    log_path = Path("app.log")
    install_crash_handlers(notify=messages.append, log_path=log_path)
    error = _raised(ValueError("kaboom"))

    with caplog.at_level(logging.CRITICAL):
        sys.excepthook(type(error), error, error.__traceback__)

    assert len(messages) == 1
    assert "ValueError: kaboom" in messages[0]
    assert str(log_path) in messages[0]
    assert "Unhandled exception" in caplog.text
    assert "kaboom" in caplog.text


def test_worker_thread_exception_is_reported() -> None:
    messages: list[str] = []
    install_crash_handlers(notify=messages.append)

    def _explode() -> None:
        msg = "worker-boom"
        raise RuntimeError(msg)

    worker = threading.Thread(target=_explode)
    worker.start()
    worker.join()

    assert len(messages) == 1
    assert "RuntimeError: worker-boom" in messages[0]


def test_keyboard_interrupt_keeps_default_behavior() -> None:
    messages: list[str] = []
    delegated: list[type[BaseException]] = []
    crash_reporting._original_excepthook = (
        lambda error_type, _error, _traceback: delegated.append(error_type)
    )
    install_crash_handlers(notify=messages.append)
    error = _raised(KeyboardInterrupt())

    sys.excepthook(type(error), error, error.__traceback__)

    assert delegated == [KeyboardInterrupt]
    assert messages == []


def test_failing_notifier_does_not_recurse(caplog) -> None:
    calls: list[str] = []

    def _failing_notify(message: str) -> None:
        calls.append(message)
        nested = _raised(RuntimeError("dialog-boom"))
        sys.excepthook(type(nested), nested, nested.__traceback__)
        raise nested

    install_crash_handlers(notify=_failing_notify)
    error = _raised(ValueError("first"))

    with caplog.at_level(logging.ERROR):
        sys.excepthook(type(error), error, error.__traceback__)

    assert len(calls) == 1
    assert "Could not report an unhandled exception" in caplog.text


def test_crash_message_omits_log_path_when_unknown() -> None:
    message = crash_message(ValueError("kaboom"), None)

    assert "ValueError: kaboom" in message
    assert "Details were written to" not in message


def test_qt_notifier_shows_dialog_on_gui_thread(monkeypatch) -> None:
    application = _app()
    shown: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        staticmethod(lambda _parent, _title, text: shown.append(text)),
    )
    notifier = QtCrashNotifier(application)

    notifier.notify("crashed")
    assert shown == []

    for _ in range(3):
        application.processEvents()

    assert shown == ["crashed"]


def test_qt_notifier_drops_reports_while_dialog_is_open(monkeypatch) -> None:
    application = _app()
    shown: list[str] = []
    notifier = QtCrashNotifier(application)

    def _reentrant_critical(_parent, _title, text: str) -> None:
        shown.append(text)
        notifier.notify("second")
        for _ in range(3):
            application.processEvents()

    monkeypatch.setattr(
        QMessageBox,
        "critical",
        staticmethod(_reentrant_critical),
    )

    notifier.notify("first")
    for _ in range(3):
        application.processEvents()

    assert shown == ["first"]
