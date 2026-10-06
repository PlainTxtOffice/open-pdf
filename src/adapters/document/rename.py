"""Filesystem adapter for safely renaming an open PDF document."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.adapters.document.replacement import FileReplacement
from src.domains.document.errors import PDF_IO_ERRORS

if TYPE_CHECKING:
    from pathlib import Path

    from src.domains.document.reader import PdfDocument


@dataclass(frozen=True, slots=True)
class RenameDestination:
    """Prepared rename destination and optional replacement backup."""

    target_path: Path
    backup_path: Path | None = None


class DocumentFileRenamer:
    """Coordinate document save-as, rollback, and old-file cleanup."""

    def __init__(self, files: FileReplacement | None = None) -> None:
        """Initialize the renamer with an optional file replacement adapter."""
        self._files = files or FileReplacement()

    def destination_exists(self, path: Path) -> bool:
        """Return whether a rename destination already exists."""
        return self._files.exists(path)

    def prepare_destination(self, path: Path) -> RenameDestination:
        """Prepare a destination, backing up an existing file."""
        backup_path = (
            self._files.backup(path) if self._files.exists(path) else None
        )
        return RenameDestination(path, backup_path)

    def save_document(
        self,
        *,
        document: PdfDocument,
        destination: RenameDestination,
    ) -> str | None:
        """Save to the destination, restoring its backup on failure."""
        try:
            document.save_as(destination.target_path)
        except PDF_IO_ERRORS as error:
            restore_error = self._files.restore(
                target_path=destination.target_path,
                backup_path=destination.backup_path,
            )
            if restore_error is None:
                return f"Failed to rename PDF:\n{error}"
            return (
                f"Failed to rename PDF:\n{error}\n\n"
                "The original destination file could not be restored:\n"
                f"{restore_error}"
            )
        return None

    def cleanup(
        self,
        *,
        source_path: Path,
        destination: RenameDestination,
    ) -> tuple[str, ...]:
        """Remove the old source and temporary replacement backup."""
        errors: list[str] = []
        self._append_cleanup_error(
            path=source_path,
            prefix="could not remove the old file",
            errors=errors,
        )
        if destination.backup_path is not None:
            self._append_cleanup_error(
                path=destination.backup_path,
                prefix="could not remove the overwritten destination backup",
                errors=errors,
            )
        return tuple(errors)

    def restore_destination(
        self,
        destination: RenameDestination,
    ) -> OSError | None:
        """Restore a prepared destination when the operation is abandoned."""
        return self._files.restore(
            target_path=destination.target_path,
            backup_path=destination.backup_path,
        )

    def _append_cleanup_error(
        self,
        *,
        path: Path,
        prefix: str,
        errors: list[str],
    ) -> None:
        error = self._files.remove(path)
        if error is not None:
            errors.append(f"{prefix}:\n{error}")
