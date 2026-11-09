"""Linux paths must respect XDG and never create files during import."""

import runpy
from pathlib import Path

import pytest

from open_pdf.application.startup import prepare_storage
from open_pdf.config import path_handler as paths


@pytest.mark.parametrize("override", ["", "relative/path"])
def test_invalid_override_uses_home_default(tmp_path, override):
    default = tmp_path / ".config"
    assert paths.xdg_directory({"XDG_CONFIG_HOME": override},
                               "XDG_CONFIG_HOME", default) == default / "open-pdf"


def test_absolute_override_is_used(tmp_path):
    override = tmp_path / "config"
    assert paths.xdg_directory({"XDG_CONFIG_HOME": str(override)},
                               "XDG_CONFIG_HOME", tmp_path) == override / "open-pdf"


def test_import_does_not_touch_filesystem(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Import must not create storage")

    monkeypatch.setattr(Path, "mkdir", unexpected)
    runpy.run_path(paths.__file__)


def test_startup_creates_only_xdg_directories(tmp_path, monkeypatch):
    from open_pdf.application import startup

    directories = [tmp_path / name for name in ("config", "cache", "logs")]
    for name, directory in zip(("CONFIG_DIR", "CACHE_DIR", "LOGS_DIR"), directories):
        monkeypatch.setattr(startup, name, directory)
    prepare_storage()
    assert set(tmp_path.iterdir()) == set(directories)
    assert all(directory.is_dir() for directory in directories)


def test_assets_are_inside_installable_package():
    assert paths.ASSETS_DIR == Path(paths.__file__).resolve().parents[1] / "assets"
    assert (paths.ASSETS_DIR / "open_pdf.png").is_file()
