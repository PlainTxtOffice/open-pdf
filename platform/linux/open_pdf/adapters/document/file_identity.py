"""File-path comparison helpers for the document lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def references_same_file(path: Path, other: Path) -> bool:
    """Return whether two paths point at the same underlying file."""
    try:
        if path.exists() and other.exists():
            return path.samefile(other)
    except OSError:
        pass

    return path.expanduser().resolve(
        strict=False,
    ) == other.expanduser().resolve(strict=False)
