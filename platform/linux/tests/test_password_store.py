"""Remembered passwords use Secret Service with case-sensitive identities."""

from keyring.errors import KeyringLocked

from open_pdf.adapters.persistence.passwords import DocumentPasswordStore


def test_case_distinct_paths_have_separate_credentials(tmp_path):
    store = DocumentPasswordStore()
    first, second = tmp_path / "Report.pdf", tmp_path / "report.pdf"
    assert store.remember(path=first, password="first")
    assert store.remember(path=second, password="second")
    assert store.recall(first) == "first"
    assert store.recall(second) == "second"
    assert list(tmp_path.iterdir()) == []


def test_unavailable_keyring_never_writes_a_password_file(tmp_path):
    store = DocumentPasswordStore()
    store._backend = None
    path = tmp_path / "document.pdf"
    assert not store.remember(path=path, password="secret")
    assert store.recall(path) is None
    store.forget(path)
    assert list(tmp_path.iterdir()) == []


def test_locked_keyring_allows_manual_password_entry(tmp_path, monkeypatch):
    store = DocumentPasswordStore()

    def locked(*args):
        raise KeyringLocked("User cancelled unlock")

    monkeypatch.setattr(store._backend, "get_password", locked)
    monkeypatch.setattr(store._backend, "set_password", locked)
    path = tmp_path / "document.pdf"
    assert store.recall(path) is None
    assert not store.remember(path=path, password="secret")


def test_rename_keeps_old_password_if_new_entry_cannot_be_saved(tmp_path, monkeypatch):
    store = DocumentPasswordStore()
    old, new = tmp_path / "old.pdf", tmp_path / "new.pdf"
    assert store.remember(path=old, password="secret")
    monkeypatch.setattr(store, "remember", lambda **kwargs: False)
    store.move(source_path=old, target_path=new)
    assert store.recall(old) == "secret"


def test_rename_moves_password_and_removes_old_entry(tmp_path):
    store = DocumentPasswordStore()
    old, new = tmp_path / "old.pdf", tmp_path / "new.pdf"
    assert store.remember(path=old, password="secret")
    store.move(source_path=old, target_path=new)
    assert store.recall(old) is None
    assert store.recall(new) == "secret"
