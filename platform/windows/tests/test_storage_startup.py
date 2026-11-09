"""Protect startup ordering and migration before portable-folder probing."""

import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

from open_pdf.application import startup
from open_pdf.config import path_handler as paths


@pytest.fixture
def storage_paths(tmp_path, monkeypatch):
    for name in ("STORAGE_MODE", "ROOT_DIR", "LOGS_DIR", "DATA_DIR"):
        monkeypatch.setattr(paths, name, getattr(paths, name))
    monkeypatch.setattr(paths, "EXE_DIR", tmp_path / "exe")
    monkeypatch.setattr(paths, "USER_DATA_DIR", tmp_path / "local" / "open-pdf")
    monkeypatch.setattr(paths, "IS_COMPILED", True)
    monkeypatch.setattr(paths, "IS_PORTABLE", True)
    return paths


def test_migration_precedes_creation_of_portable_folder(storage_paths):
    legacy = paths.EXE_DIR / paths.LEGACY_PORTABLE_DATA_DIR_NAME
    legacy.mkdir(parents=True)
    (legacy / "settings.txt").write_text("keep", encoding="utf-8")

    startup.prepare_storage()

    assert not legacy.exists()
    assert paths.ROOT_DIR == paths.EXE_DIR / paths.PORTABLE_DATA_DIR_NAME
    assert (paths.ROOT_DIR / "settings.txt").read_text(encoding="utf-8") == "keep"
    assert paths.DATA_DIR == paths.ROOT_DIR / "data"
    assert paths.LOGS_DIR == paths.ROOT_DIR / "logs"


def test_portable_fallback_uses_migrated_user_storage(storage_paths, monkeypatch):
    legacy = paths.USER_DATA_DIR.with_name(paths.LEGACY_APP_DATA_DIR_NAME)
    legacy.mkdir(parents=True)
    (legacy / "settings.txt").write_text("keep", encoding="utf-8")
    monkeypatch.setattr(startup, "is_writable_dir", lambda path: False)

    startup.prepare_storage()

    assert paths.STORAGE_MODE == "portable-fallback"
    assert paths.ROOT_DIR == paths.USER_DATA_DIR
    assert (paths.DATA_DIR.parent / "settings.txt").read_text(encoding="utf-8") == "keep"


def test_development_does_not_touch_user_storage(storage_paths, monkeypatch):
    monkeypatch.setattr(paths, "IS_COMPILED", False)

    def unexpected(*args):
        raise AssertionError("Development must not migrate or probe user storage")

    monkeypatch.setattr(startup, "migrate_legacy_folder", unexpected)
    monkeypatch.setattr(startup, "is_writable_dir", unexpected)
    startup.prepare_storage()
    assert paths.STORAGE_MODE == "development"
    assert paths.ROOT_DIR == paths.DEV_ROOT


def test_importing_compiled_paths_does_not_write(tmp_path, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Path import must not create or move folders")

    monkeypatch.setattr(Path, "mkdir", unexpected)
    monkeypatch.setattr(Path, "rename", unexpected)
    module = runpy.run_path(
        paths.__file__,
        init_globals={"__compiled__": SimpleNamespace(containing_dir=str(tmp_path))},
    )
    assert module["IS_COMPILED"] is True
