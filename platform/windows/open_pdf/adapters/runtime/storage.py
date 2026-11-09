"""Probe writable storage and migrate legacy folders at startup."""

from __future__ import annotations

import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def is_writable_dir(path: Path) -> bool:
    """Return whether the app can create files in the folder.

    - Creates the folder when missing, then writes a temporary probe file,
      because os.access does not reflect Windows folder permissions.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=path):
            pass
    except OSError:
        return False
    return True


def migrate_legacy_folder(legacy: Path, current: Path) -> bool:
    """Rename a data folder left under an earlier name to the current name.

    - Moves only when the legacy folder exists and the current one does not,
      so it never merges or overwrites data.
    - Leaves the legacy folder in place when the rename fails, and the app
      then starts with a new folder.
    """
    if current.exists() or not legacy.is_dir():
        return False
    try:
        legacy.rename(current)
    except OSError:
        return False
    return True
