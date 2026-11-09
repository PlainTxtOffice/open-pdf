"""Isolate Qt, all writable paths, and native credential access in tests."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


class MemoryKeychain:
    def __init__(self):
        self.values = {}

    def set_password(self, service, username, password):
        self.values[service, username] = password

    def get_password(self, service, username):
        return self.values.get((service, username))

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


@pytest.fixture(autouse=True)
def isolate_persistence(monkeypatch, tmp_path):
    from open_pdf.config import path_handler as paths
    from open_pdf.adapters.persistence import passwords
    from open_pdf.gui.views.root_window import window

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(paths, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(paths, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(window, "_PANE_SETTINGS_PATH", tmp_path / "ui.json")
    monkeypatch.setattr(window, "_DOCUMENT_PASSWORDS_PATH", tmp_path / "unused")
    monkeypatch.setattr(window, "_OCR_CACHE_DIRECTORY", tmp_path / "ocr")
    backend = MemoryKeychain()
    monkeypatch.setattr(passwords, "native_keychain", lambda: backend)
