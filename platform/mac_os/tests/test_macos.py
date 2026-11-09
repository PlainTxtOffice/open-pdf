"""Native integration contracts testable without touching a user's Mac."""

from pathlib import Path
import os
import subprocess
import sys

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QFileOpenEvent, QKeySequence, QAction
from PySide6.QtWidgets import QApplication

from open_pdf.adapters.persistence.passwords import DocumentPasswordStore
from open_pdf.application.startup import prepare_storage
from open_pdf.config import path_handler as paths
from open_pdf.gui.application import MacApplication
from open_pdf.gui.app import MainWindow


def test_storage_uses_library_without_creating_paths(tmp_path):
    home = tmp_path / "unused-home"
    data, cache, logs = paths.storage_paths(home)
    assert data == home / "Library/Application Support/Open PDF"
    assert cache == home / "Library/Caches/Open PDF"
    assert logs == home / "Library/Logs/Open PDF"
    assert not home.exists()


def test_startup_creates_only_native_storage():
    prepare_storage()
    assert all(p.is_dir() for p in (paths.DATA_DIR, paths.CACHE_DIR, paths.LOGS_DIR))


def test_keychain_unavailable_never_creates_password_file(tmp_path, monkeypatch):
    from open_pdf.adapters.persistence import passwords

    monkeypatch.setattr(passwords, "native_keychain", lambda: None)
    file = tmp_path / "passwords.json"
    store = DocumentPasswordStore(file)
    assert store.remember(path=tmp_path / "private.pdf", password="secret") is False
    assert store.recall(tmp_path / "private.pdf") is None
    assert not file.exists()


def test_keychain_move_preserves_secret_if_destination_fails(tmp_path):
    class LockedDestination:
        deleted = False

        def get_password(self, *args):
            return "secret"

        def set_password(self, *args):
            raise RuntimeError("locked")

        def delete_password(self, *args):
            self.deleted = True

    backend = LockedDestination()
    store = DocumentPasswordStore(tmp_path / "unused", backend=backend)
    store.move(source_path=tmp_path / "a.pdf", target_path=tmp_path / "b.pdf")
    assert not backend.deleted


def test_keychain_case_sensitive_paths_remain_distinct(tmp_path):
    store = DocumentPasswordStore(tmp_path / "unused")
    upper, lower = tmp_path / "A.pdf", tmp_path / "a.pdf"
    store.remember(path=upper, password="upper")
    store.remember(path=lower, password="lower")
    assert store.recall(upper) == "upper"
    assert store.recall(lower) == "lower"


def test_finder_requests_are_queued_and_delivered_in_order(tmp_path):
    # QApplication cannot be replaced in-process after other GUI tests run.
    # Exercise the real Qt event handler with a lightweight queue owner.
    class Receiver:
        _window = None
        _pending = []
        open_file = MacApplication.open_file

    class Window:
        opened = []
        presentations = 0

        def present(self):
            self.presentations += 1

        def open_document_in_tab(self, path):
            self.opened.append(path)

    receiver = Receiver()
    window = Window()
    first, second = tmp_path / "first.pdf", tmp_path / "second.pdf"
    assert MacApplication.event(receiver, QFileOpenEvent(str(first)))
    assert window.opened == []
    MacApplication.attach_window(receiver, window)
    assert MacApplication.event(receiver, QFileOpenEvent(QUrl.fromLocalFile(str(second))))
    assert window.opened == [first.resolve(), second.resolve()]
    assert window.presentations == 2
    assert receiver._pending == []
    assert not MacApplication.event(receiver, QFileOpenEvent(QUrl("https://example.com/a.pdf")))


def test_native_menu_shortcuts_and_roles():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    for action, key in (
        (window._open_action, QKeySequence.StandardKey.Open),
        (window._save_action, QKeySequence.StandardKey.Save),
        (window._save_as_action, QKeySequence.StandardKey.SaveAs),
        (window._print_action, QKeySequence.StandardKey.Print),
        (window._close_tab_action, QKeySequence.StandardKey.Close),
        (window._exit_action, QKeySequence.StandardKey.Quit),
    ):
        assert action.shortcut() == QKeySequence(key)
    assert window._exit_action.menuRole() == QAction.MenuRole.QuitRole
    assert window._about_action.menuRole() == QAction.MenuRole.AboutRole
    window.close()
    QCoreApplication.processEvents()


def test_real_application_opens_finder_document(tmp_path):
    script = '''
import sys
from pathlib import Path
import pymupdf
from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtGui import QFileOpenEvent
from open_pdf.config import path_handler as paths

root = Path(sys.argv[1])
paths.DATA_DIR = root / "data"
paths.CACHE_DIR = root / "cache"
paths.LOGS_DIR = root / "logs"
from open_pdf.application.startup import prepare_storage
prepare_storage()
from open_pdf.gui.application import MacApplication
from open_pdf.gui.app import MainWindow

source = root / "Finder document.pdf"
with pymupdf.open() as document:
    document.new_page().insert_text((72, 72), "Finder smoke test")
    document.save(source)
application = MacApplication([])
QCoreApplication.sendEvent(application, QFileOpenEvent(str(source)))
window = MainWindow()
application.attach_window(window)
assert window._document.source_path == source
assert window._document.state.page_count == 1
QCoreApplication.sendEvent(application, QFileOpenEvent(str(source)))
assert len(window._tab_sessions) == 1
window.show()
QTimer.singleShot(100, window.close)
assert application.exec() == 0
'''
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        env=environment, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
