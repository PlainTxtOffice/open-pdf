"""Tests for development and packaged runtime paths."""

from pathlib import Path
from types import SimpleNamespace

from src.config import path_handler


def test_packaged_storage_uses_local_app_data(monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\Example\AppData\Local")

    assert path_handler._packaged_storage_root() == Path(
        r"C:\Users\Example\AppData\Local\Open PDF",
    )


def test_packaged_storage_has_home_fallback(monkeypatch) -> None:
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(Path, "home", lambda: Path(r"C:\Users\Example"))

    assert path_handler._packaged_storage_root() == Path(
        r"C:\Users\Example\.open-pdf",
    )


def test_bundled_marker_selects_the_portable_build(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / path_handler.PORTABLE_MARKER_NAME).touch()
    monkeypatch.setattr(path_handler, "IS_COMPILED", True)
    monkeypatch.setattr(path_handler, "ROOT_DIR", tmp_path)

    assert path_handler._is_portable_build() is True


def test_missing_marker_leaves_the_build_non_portable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(path_handler, "IS_COMPILED", True)
    monkeypatch.setattr(path_handler, "ROOT_DIR", tmp_path)

    assert path_handler._is_portable_build() is False


def test_source_checkout_is_never_portable(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / path_handler.PORTABLE_MARKER_NAME).touch()
    monkeypatch.setattr(path_handler, "IS_COMPILED", False)
    monkeypatch.setattr(path_handler, "ROOT_DIR", tmp_path)

    assert path_handler._is_portable_build() is False


def test_storage_root_prefers_portable_over_local_app_data(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / path_handler.PORTABLE_MARKER_NAME).touch()
    monkeypatch.setattr(path_handler, "IS_COMPILED", True)
    monkeypatch.setattr(path_handler, "ROOT_DIR", tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\Example\AppData\Local")
    monkeypatch.setattr(
        path_handler,
        "__compiled__",
        SimpleNamespace(containing_dir=r"D:\Portable"),
        raising=False,
    )

    assert path_handler._user_storage_root() == Path(
        r"D:\Portable\Open PDF Data",
    )


def test_storage_root_uses_local_app_data_without_a_marker(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(path_handler, "IS_COMPILED", True)
    monkeypatch.setattr(path_handler, "ROOT_DIR", tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\Example\AppData\Local")

    assert path_handler._user_storage_root() == Path(
        r"C:\Users\Example\AppData\Local\Open PDF",
    )


def test_storage_root_is_the_repository_in_a_source_checkout(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(path_handler, "IS_COMPILED", False)
    monkeypatch.setattr(path_handler, "ROOT_DIR", tmp_path)

    assert path_handler._user_storage_root() == tmp_path


def test_portable_storage_uses_the_nuitka_containing_directory(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        path_handler,
        "__compiled__",
        SimpleNamespace(containing_dir=r"D:\Portable"),
        raising=False,
    )

    assert path_handler._portable_storage_root() == Path(
        r"D:\Portable\Open PDF Data",
    )


def test_portable_storage_falls_back_to_the_launched_executable(
    monkeypatch,
) -> None:
    monkeypatch.delattr(path_handler, "__compiled__", raising=False)
    monkeypatch.setattr(
        path_handler.sys,
        "argv",
        [r"D:\Fallback\Open PDF.exe"],
    )

    assert path_handler._portable_storage_root() == Path(
        r"D:\Fallback\Open PDF Data",
    )


def test_portable_storage_ignores_the_unpacked_interpreter_path(
    monkeypatch,
) -> None:
    """sys.executable points into the onefile temp dir, which is deleted."""
    monkeypatch.setattr(
        path_handler,
        "__compiled__",
        SimpleNamespace(containing_dir=r"D:\Portable"),
        raising=False,
    )
    monkeypatch.setattr(
        path_handler.sys,
        "executable",
        r"C:\Users\Example\AppData\Local\Temp\onefile_123\python.exe",
    )

    assert path_handler._portable_storage_root() == Path(
        r"D:\Portable\Open PDF Data",
    )
