"""Launch a source or compiled app against a disposable PDF and user profile."""

import argparse
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import pymupdf


def smoke_test(command: list[str]) -> None:
    """Require the real GUI to open and rasterize a page before exiting."""
    with tempfile.TemporaryDirectory(prefix="open-pdf-smoke-") as directory:
        root = Path(directory)
        pdf = root / "sample.pdf"
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((72, 72), "Open PDF Linux smoke test")
            document.save(pdf)
        env = os.environ.copy()
        for name in ("CONFIG", "CACHE", "STATE", "DATA", "RUNTIME"):
            location = root / name.lower()
            location.mkdir(mode=0o700)
            env[f"XDG_{name}_HOME" if name != "RUNTIME" else
                "XDG_RUNTIME_DIR"] = str(location)
        env["HOME"] = str(root)
        env.setdefault("QT_QPA_PLATFORM", "xcb")
        env["PYTHONFAULTHANDLER"] = "1"
        try:
            result = subprocess.run(
                [*command, "--smoke-test", str(pdf)], env=env, cwd=root,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding="utf-8", errors="replace", timeout=60, check=False,
            )
        except subprocess.TimeoutExpired as error:
            output = error.stdout or b""
            print(output.decode("utf-8", errors="replace"), flush=True)
            raise
        print(result.stdout.strip(), flush=True)
        result.check_returncode()
        if "OPEN_PDF_SMOKE_OK" not in result.stdout:
            raise RuntimeError("GUI did not confirm rendering")


def test_archive(path: Path) -> None:
    """Test the deliverable after extraction, outside the source directory."""
    with tempfile.TemporaryDirectory(prefix="open-pdf-extract-") as directory:
        with tarfile.open(path) as archive:
            archive.extractall(directory, filter="data")
        executables = list(Path(directory).glob("*/open-pdf"))
        if len(executables) != 1 or not os.access(executables[0], os.X_OK):
            raise RuntimeError("Archive must contain one executable open-pdf")
        smoke_test([str(executables[0])])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", nargs="?", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    if args.archive:
        test_archive(args.archive)
    else:
        command = ([str(args.executable.resolve())] if args.executable else
                   [sys.executable, "-m", "open_pdf.main"])
        smoke_test(command)
