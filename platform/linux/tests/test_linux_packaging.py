"""Check archive contents and data bundling without compiling on the host."""

import importlib.util
import sys
import tarfile
from pathlib import Path

import pytest


@pytest.fixture
def build_module(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("linux_build", scripts / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_archive_contains_full_payload_and_not_build_workspace(build_module, tmp_path, monkeypatch):
    project = tmp_path / "platform/linux"
    dist = project / "build/nuitka/main.dist"
    (dist / "plugins").mkdir(parents=True)
    (dist / "open-pdf").write_bytes(b"executable")
    (dist / "plugins/libqxcb.so").write_bytes(b"plugin")
    (project / "build/private.env").write_text("not distributed", encoding="utf-8")
    (project / "assets").mkdir()
    for name in ("README.md", "THIRD_PARTY.md", "assets/com.plaintxtoffice.OpenPDF.desktop"):
        (project / name).write_text("notice", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("MIT", encoding="utf-8")
    monkeypatch.setattr(build_module, "PROJECT", project)
    monkeypatch.setattr(build_module.importlib.metadata, "version", lambda name: "1")
    archive_path = build_module.package_archive(dist, "0.1.0")
    with tarfile.open(archive_path) as archive:
        names = archive.getnames()
    root = "open-pdf-0.1.0-linux-x86_64"
    assert f"{root}/open-pdf" in names
    assert f"{root}/plugins/libqxcb.so" in names
    assert f"{root}/build-info.json" in names
    assert f"{root}/LICENSE" in names
    assert not any("private.env" in name for name in names)


def test_compiler_only_bundles_required_application_data(build_module):
    arguments = build_module.compiler_arguments()
    data_options = [arg for arg in arguments if arg.startswith("--include-data")]
    assert data_options == [
        "--include-data-files=open_pdf/assets/open_pdf.png=open_pdf/assets/open_pdf.png",
    ]
    assert not any("windows" in arg.lower() for arg in arguments[2:])


def test_build_rejects_windows_before_compilation(build_module, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(SystemExit, match="x86-64 Linux"):
        build_module.main()
