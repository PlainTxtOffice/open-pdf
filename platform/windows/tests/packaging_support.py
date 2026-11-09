"""Run packaging scripts against isolated inputs and a simulated compiler."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh")

COMPILER = '''import json, os, subprocess, sys
from pathlib import Path

args = sys.argv[1:]
if args[:2] == ["-m", "nuitka"]:
    if "--plugin-list" in args:
        if os.environ.get("TEST_PLUGIN_ERROR"):
            sys.exit(9)
        print("data-hiding Commercial" if os.environ.get("TEST_COMMERCIAL") else "pyside6")
        sys.exit(0)
    Path(os.environ["TEST_BUILD_ARGS"]).write_text(json.dumps(args), encoding="utf-8")
    if os.environ.get("TEST_BUILD_ERROR"):
        sys.exit(12)
    output = Path(next(a.split("=", 1)[1] for a in args if a.startswith("--output-dir=")))
    filename = next(a.split("=", 1)[1] for a in args if a.startswith("--output-filename="))
    dist = output / "main.dist"
    dist.mkdir(parents=True)
    (dist / filename).write_bytes(b"MZ")
    if "--onefile" in args:
        (output / filename).write_bytes(b"MZ")
    if os.environ.get("TEST_PRIVATE"):
        value = os.environ["USERNAME"]
        (dist / "notes.txt").write_bytes(value.encode("utf-16le"))
        # Straddle the bounded reader's one-megabyte boundary.
        (dist / "settings.json").write_bytes(b"x" * (1024 * 1024 - 3) + value.encode())
        (dist / "image.png").write_text(value, encoding="utf-8")
    if os.environ.get("TEST_DIRTY"):
        (dist / ".env").write_text("private", encoding="utf-8")
    sys.exit(0)
if args[:1] == ["-c"] and args[1] in ("import compression.zstd", "import zstandard"):
    wanted = "stdlib" if args[1] == "import compression.zstd" else "package"
    sys.exit(0 if os.environ.get("TEST_COMPRESSION", "stdlib") == wanted else 1)
sys.exit(subprocess.run([sys.executable, *args]).returncode)
'''


def make_project(tmp_path):
    """Copy maintained scripts and minimal real app inputs into a fixture."""
    project = tmp_path / "repo" / "platform" / "windows"
    scripts = project / "scripts" / "nuitka"
    shutil.copytree(PROJECT / "scripts" / "nuitka", scripts)
    shutil.copy(PROJECT / "pyproject.toml", project)
    (project / "assets").mkdir()
    shutil.copy(PROJECT / "assets" / "open_pdf.ico", project / "assets")
    config = project / "open_pdf" / "config"
    config.mkdir(parents=True)
    shutil.copy(PROJECT / "open_pdf" / "config" / "path_handler.py", config)
    compiler = project / "compiler.py"
    compiler.write_text(COMPILER, encoding="utf-8")
    shim = project / "python.ps1"
    python = sys.executable.replace("'", "''")
    script = str(compiler).replace("'", "''")
    shim.write_text(f"& '{python}' '{script}' @args\n", encoding="utf-8")
    return project, shim


def run_script(project, shim, name, *args, **environment):
    """Exercise PowerShell without compiling, signing, or touching user data."""
    env = dict(os.environ)
    env.update(
        LOCALAPPDATA=str(project / "local-appdata"),
        USERNAME="test-private-user",
        TEST_BUILD_ARGS=str(project / "build-arguments.json"),
        WINDOWS_CERTIFICATE_SHA1="A" * 40,
    )
    env.update(environment)
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-File",
         str(project / "scripts" / "nuitka" / name),
         "-PythonExecutable", str(shim), *args],
        cwd=project.parent,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=45,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def arguments(project):
    """Read arguments captured at the external compiler boundary."""
    return json.loads((project / "build-arguments.json").read_text("utf-8"))
