"""Tests for development and packaged runtime paths."""

import tomllib
from pathlib import Path
from types import SimpleNamespace

from open_pdf.config import path_handler
from open_pdf.adapters.runtime import storage

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _resolve(
    tmp_path: Path,
    *,
    is_compiled: bool,
    is_portable: bool,
    writable: bool = True,
) -> tuple[str, Path]:
    return path_handler.resolve_storage(
        is_compiled=is_compiled,
        is_portable=is_portable,
        exe_dir=tmp_path / "exe",
        user_data_dir=tmp_path / "local" / path_handler.APP_DATA_DIR_NAME,
        is_writable=lambda _path: writable,
    )


def test_app_data_dir_matches_pyproject() -> None:
    """pyproject.toml is not inside a compiled build, so the names must agree."""
    metadata = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))

    assert (
        metadata["tool"]["open-pdf"]["app-data-dir"]
        == path_handler.APP_DATA_DIR_NAME
    )


def test_user_data_uses_local_app_data() -> None:
    environ = {"LOCALAPPDATA": r"C:\Users\Example\AppData\Local"}

    assert path_handler.resolve_user_data_dir(environ) == Path(
        r"C:\Users\Example\AppData\Local\open-pdf",
    )


def test_user_data_has_home_fallback(monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: Path(r"C:\Users\Example"))

    assert path_handler.resolve_user_data_dir({}) == Path(
        r"C:\Users\Example\AppData\Local\open-pdf",
    )


def test_source_checkout_stores_data_in_the_project(tmp_path: Path) -> None:
    assert _resolve(tmp_path, is_compiled=False, is_portable=True) == (
        "development",
        path_handler.DEV_ROOT,
    )


def test_build_without_a_marker_uses_local_app_data(tmp_path: Path) -> None:
    assert _resolve(tmp_path, is_compiled=True, is_portable=False) == (
        "installed",
        tmp_path / "local" / "open-pdf",
    )


def test_storage_root_prefers_portable_over_local_app_data(
    tmp_path: Path,
) -> None:
    assert _resolve(tmp_path, is_compiled=True, is_portable=True) == (
        "portable",
        tmp_path / "exe" / "open-pdf-data",
    )


def test_read_only_portable_folder_falls_back_to_local_app_data(
    tmp_path: Path,
) -> None:
    assert _resolve(
        tmp_path,
        is_compiled=True,
        is_portable=True,
        writable=False,
    ) == ("portable-fallback", tmp_path / "local" / "open-pdf")


def test_writable_probe_creates_the_folder(tmp_path: Path) -> None:
    target = tmp_path / "new" / "open-pdf-data"

    assert storage.is_writable_dir(target) is True
    assert target.is_dir()
    assert list(target.iterdir()) == []


def test_writable_probe_rejects_a_file_path(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")

    assert storage.is_writable_dir(blocker / "open-pdf-data") is False


def test_portable_storage_sits_beside_the_onefile_binary(monkeypatch) -> None:
    monkeypatch.setattr(
        path_handler,
        "__compiled__",
        SimpleNamespace(containing_dir=r"D:\Portable"),
        raising=False,
    )

    assert path_handler.resolve_exe_dir() == Path(r"D:\Portable").resolve()


def test_exe_dir_falls_back_to_the_launched_executable(monkeypatch) -> None:
    monkeypatch.delattr(path_handler, "__compiled__", raising=False)
    monkeypatch.setattr(
        path_handler.sys,
        "argv",
        [r"D:\Fallback\Open PDF.exe"],
    )

    assert path_handler.resolve_exe_dir() == Path(r"D:\Fallback").resolve()


def test_exe_dir_ignores_the_unpacked_interpreter_path(monkeypatch) -> None:
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

    assert path_handler.resolve_exe_dir() == Path(r"D:\Portable").resolve()


def test_source_checkout_is_never_portable() -> None:
    assert path_handler.IS_COMPILED is False
    assert path_handler.IS_PORTABLE is False
    assert path_handler.STORAGE_MODE == "development"


def test_legacy_folder_is_renamed_when_only_it_exists(tmp_path: Path) -> None:
    legacy = tmp_path / "Open PDF Data"
    (legacy / "data").mkdir(parents=True)
    (legacy / "data" / "ui-state.json").write_text("{}", encoding="utf-8")
    current = tmp_path / "open-pdf-data"

    assert storage.migrate_legacy_folder(legacy, current) is True
    assert not legacy.exists()
    assert (current / "data" / "ui-state.json").read_text(
        encoding="utf-8",
    ) == "{}"


def test_legacy_folder_never_overwrites_current_data(tmp_path: Path) -> None:
    legacy = tmp_path / "Open PDF"
    legacy.mkdir()
    current = tmp_path / "open-pdf"
    current.mkdir()
    (current / "keep.txt").write_text("current", encoding="utf-8")

    assert storage.migrate_legacy_folder(legacy, current) is False
    assert legacy.is_dir()
    assert (current / "keep.txt").read_text(encoding="utf-8") == "current"


def test_missing_legacy_folder_is_ignored(tmp_path: Path) -> None:
    current = tmp_path / "open-pdf"

    assert (
        storage.migrate_legacy_folder(tmp_path / "Open PDF", current)
        is False
    )
    assert not current.exists()


def test_failed_rename_keeps_the_legacy_folder(
    tmp_path: Path,
    monkeypatch,
) -> None:
    legacy = tmp_path / "Open PDF"
    legacy.mkdir()

    def locked(self: Path, target: Path) -> Path:
        raise PermissionError("in use")

    monkeypatch.setattr(Path, "rename", locked)

    assert (
        storage.migrate_legacy_folder(legacy, tmp_path / "open-pdf")
        is False
    )
    assert legacy.is_dir()
