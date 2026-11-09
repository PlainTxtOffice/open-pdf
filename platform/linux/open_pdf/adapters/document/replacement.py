"""Filesystem adapter for safe document replacement and cleanup."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from pathlib import Path


class FileReplacement:
    """Manage temporary replacement backups and file cleanup."""

    @staticmethod
    def exists(path: Path) -> bool:
        """Return whether a path currently exists."""
        return path.exists()

    def backup(self, path: Path) -> Path:
        """Move an existing target to a unique temporary backup."""
        backup_path = self._backup_path(path)
        path.replace(backup_path)
        return backup_path

    @staticmethod
    def restore(
        *,
        target_path: Path,
        backup_path: Path | None,
    ) -> OSError | None:
        """Restore a replacement backup, returning any filesystem error."""
        if backup_path is None or not backup_path.exists():
            return None
        try:
            backup_path.replace(target_path)
        except OSError as error:
            return error
        return None

    @staticmethod
    def remove(path: Path) -> OSError | None:
        """Remove a path if present, returning any filesystem error."""
        try:
            if path.exists():
                path.unlink()
        except OSError as error:
            return error
        return None

    @staticmethod
    def _backup_path(path: Path) -> Path:
        while True:
            backup_path = path.with_name(
                f".{path.stem}.{uuid4().hex}{path.suffix}.bak",
            )
            if not backup_path.exists():
                return backup_path
