"""Build and smoke-test an Ubuntu x86-64 standalone archive with Nuitka."""

import importlib.metadata
import json
import platform
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

from smoke_test import smoke_test

PROJECT = Path(__file__).resolve().parents[1]


def compiler_arguments() -> list[str]:
    """Bundle only the app icon and explicitly required runtime packages."""
    return [
        sys.executable, "-m", "nuitka", "--mode=standalone",
        "--enable-plugin=pyside6", "--include-qt-plugins=sensible",
        "--include-module=keyring.backends.SecretService",
        "--include-package=pytesseract", "--include-package=PIL",
        "--include-data-files=open_pdf/assets/open_pdf.png=open_pdf/assets/open_pdf.png",
        "--output-dir=build/nuitka", "--output-filename=open-pdf",
        "--report=build/compilation-report.xml", "--jobs=2", "--lto=no",
        "--assume-yes-for-downloads", "open_pdf/main.py",
    ]


def package_archive(dist: Path, version: str) -> Path:
    """Archive the validated payload, retaining executable permissions."""
    name = f"open-pdf-{version}-linux-x86_64"
    output = PROJECT / "build" / f"{name}.tar.gz"
    build_info = PROJECT / "build/build-info.json"
    build_info.write_text(json.dumps({
        "version": version,
        "python": platform.python_version(),
        "target": "Ubuntu 24.04 x86-64",
        "dependencies": {
            package: importlib.metadata.version(package)
            for package in ("Nuitka", "PySide6", "PyMuPDF", "keyring",
                            "SecretStorage", "pytesseract", "Pillow")
        },
    }, indent=2) + "\n", encoding="utf-8")
    with tarfile.open(output, "w:gz") as archive:
        archive.add(dist, arcname=name)
        for path, target in (
            (PROJECT.parents[1] / "LICENSE", "LICENSE"),
            (PROJECT / "README.md", "README.md"),
            (PROJECT / "THIRD_PARTY.md", "THIRD_PARTY.md"),
            (PROJECT / "assets/com.plaintxtoffice.OpenPDF.desktop",
             "com.plaintxtoffice.OpenPDF.desktop"),
            (build_info, "build-info.json"),
        ):
            archive.add(path, arcname=f"{name}/{target}")
    return output


def main() -> None:
    """Fail before compilation on unsupported build hosts."""
    if sys.platform != "linux" or platform.machine() != "x86_64":
        raise SystemExit("Build on an x86-64 Linux host, such as ubuntu-24.04.")
    metadata = tomllib.loads((PROJECT / "pyproject.toml").read_text("utf-8"))
    (PROJECT / "build").mkdir(exist_ok=True)
    subprocess.run(compiler_arguments(), cwd=PROJECT, check=True)
    dist = PROJECT / "build/nuitka/main.dist"
    executable = dist / "open-pdf"
    if not executable.is_file():
        raise RuntimeError(f"Nuitka did not create {executable}")
    smoke_test([str(executable)])
    print(package_archive(dist, metadata["project"]["version"]))


if __name__ == "__main__":
    main()
