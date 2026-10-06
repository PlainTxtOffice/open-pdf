"""Static/base path constants for development and packaged builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path

IS_COMPILED = bool(
    globals().get("__compiled__", False) or getattr(sys, "frozen", False),
)
#: Root holding bundled, read-only project files. Compiled builds keep this
#: module's package path, so `parents[2]` resolves to the Nuitka dist
#: directory there and to the repository root during development. The entry
#: point cannot derive this itself: Nuitka compiles `src/main.py` as
#: `__main__`, which drops the `src` path element.
ROOT_DIR = Path(__file__).resolve().parents[2]


#: Name of the empty file the portable build bundles into its dist directory.
#: Its presence is the only thing that distinguishes a portable build from an
#: installed one, so `onefile.ps1` ships it and `standalone.ps1` does not.
PORTABLE_MARKER_NAME = "portable.marker"


def _packaged_storage_root() -> Path:
    """Return writable per-user storage for a distributed Windows build."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Open PDF"
    return Path.home() / ".open-pdf"


def _is_portable_build() -> bool:
    """Return whether this build carries the bundled portable marker."""
    return IS_COMPILED and (ROOT_DIR / PORTABLE_MARKER_NAME).exists()


def _portable_storage_root() -> Path:
    """Return storage beside the executable the user actually launched.

    - A onefile build unpacks itself into a temporary directory and runs from
      there, so `sys.executable` names a throwaway interpreter that Nuitka
      deletes on exit. Writing storage there loses it on every run.
    - Nuitka reports the real location as `__compiled__.containing_dir`, which
      is correct for onefile and standalone builds alike.
    - `sys.argv[0]` holds the same path and covers a build whose Nuitka is too
      old to publish `containing_dir`.
    """
    containing_dir = getattr(
        globals().get("__compiled__"),
        "containing_dir",
        None,
    )
    if containing_dir:
        return Path(containing_dir) / "Open PDF Data"
    return Path(sys.argv[0]).resolve().parent / "Open PDF Data"


def _user_storage_root() -> Path:
    """Return the writable root this build keeps its settings and logs under."""
    if _is_portable_build():
        return _portable_storage_root()
    return _packaged_storage_root() if IS_COMPILED else ROOT_DIR


USER_STORAGE_ROOT = _user_storage_root()
LOGS_DIR = USER_STORAGE_ROOT / "logs"
DATA_DIR = USER_STORAGE_ROOT / "data"
