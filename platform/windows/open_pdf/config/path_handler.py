"""Static/base path constants for development and packaged builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

type StorageMode = Literal[
    "development",
    "portable",
    "portable-fallback",
    "installed",
]

# Keep in sync with app-data-dir in pyproject.toml; a test checks the match.
APP_DATA_DIR_NAME = "open-pdf"
PORTABLE_DATA_DIR_NAME = f"{APP_DATA_DIR_NAME}-data"
# Builds before 2026-10-28 used these folder names; compiled builds rename them.
LEGACY_APP_DATA_DIR_NAME = "Open PDF"
LEGACY_PORTABLE_DATA_DIR_NAME = "Open PDF Data"
#: Name of the empty file the portable build bundles into its dist directory.
#: Its presence is the only thing that distinguishes a portable build from an
#: installed one, so `onefile.ps1` ships it and `standalone.ps1` does not.
PORTABLE_MARKER_NAME = "portable.marker"

IS_COMPILED = bool(
    globals().get("__compiled__", False) or getattr(sys, "frozen", False),
)
#: Root holding bundled, read-only project files. Compiled builds keep this
#: module's package path, so `parents[2]` resolves to the Nuitka dist
#: directory there and to `platform/windows/` during development. The entry
#: point cannot derive this itself: Nuitka compiles `open_pdf/main.py` as
#: `__main__`, which drops the `open_pdf` path element.
DEV_ROOT = Path(__file__).resolve().parents[2]
IS_PORTABLE = IS_COMPILED and (DEV_ROOT / PORTABLE_MARKER_NAME).is_file()
ASSETS_DIR = DEV_ROOT / "assets"


def resolve_user_data_dir(environ: Mapping[str, str]) -> Path:
    """Return the per-user data folder used by installed builds.

    - Falls back to AppData/Local under the home folder when LOCALAPPDATA is
      unset or empty.
    """
    local_app_data = environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / "AppData" / "Local"
    return base / APP_DATA_DIR_NAME


def resolve_exe_dir() -> Path:
    """Return the folder that holds the launched executable.

    - A onefile build unpacks itself into a temporary directory and runs from
      there, so `sys.executable` names a throwaway interpreter that Nuitka
      deletes on exit. Writing storage there loses it on every run.
    - Nuitka reports the real location as `__compiled__.containing_dir`, which
      is correct for onefile and standalone builds alike.
    - `sys.argv[0]` holds the same path and covers a build whose Nuitka is too
      old to publish `containing_dir`.
    """
    compiled = globals().get("__compiled__")
    containing_dir = getattr(compiled, "containing_dir", None)
    if containing_dir:
        return Path(containing_dir).resolve()
    return Path(sys.argv[0]).resolve().parent


def resolve_storage(
    *,
    is_compiled: bool,
    is_portable: bool,
    exe_dir: Path,
    user_data_dir: Path,
    is_writable: Callable[[Path], bool],
) -> tuple[StorageMode, Path]:
    """Return the storage mode and root folder for writable app data.

    - Development keeps data in the Windows project folder.
    - Portable builds keep data in one folder beside the executable and fall
      back to the per-user folder when that location is read-only.
    - Installed builds use the per-user folder because Program Files is not
      writable.
    """
    if not is_compiled:
        return "development", DEV_ROOT
    if not is_portable:
        return "installed", user_data_dir
    portable_root = exe_dir / PORTABLE_DATA_DIR_NAME
    if is_writable(portable_root):
        return "portable", portable_root
    return "portable-fallback", user_data_dir


USER_DATA_DIR = resolve_user_data_dir(os.environ)
EXE_DIR = resolve_exe_dir() if IS_COMPILED else DEV_ROOT
# Startup finalizes portable writability before importing storage consumers.
STORAGE_MODE: StorageMode = (
    "development"
    if not IS_COMPILED
    else "portable"
    if IS_PORTABLE
    else "installed"
)
ROOT_DIR = (
    DEV_ROOT
    if not IS_COMPILED
    else EXE_DIR / PORTABLE_DATA_DIR_NAME
    if IS_PORTABLE
    else USER_DATA_DIR
)
LOGS_DIR = ROOT_DIR / "logs"
DATA_DIR = ROOT_DIR / "data"


def configure_storage(mode: StorageMode, root: Path) -> None:
    """Publish startup's storage selection before consumers are imported."""
    global STORAGE_MODE, ROOT_DIR, LOGS_DIR, DATA_DIR  # noqa: PLW0603
    STORAGE_MODE = mode
    ROOT_DIR = root
    LOGS_DIR = root / "logs"
    DATA_DIR = root / "data"
