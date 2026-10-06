"""Persistence facade for desktop state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.adapters.persistence.passwords import DocumentPasswordStore
from src.adapters.persistence.preferences import UiPreferencesStore

if TYPE_CHECKING:
    from pathlib import Path


class DesktopPersistence:
    """Coordinate persisted preferences and remembered PDF passwords."""

    def __init__(
        self,
        *,
        preferences_path: Path,
        passwords_path: Path,
    ) -> None:
        """Build the local persistence adapters used by the desktop app."""
        self._preferences = UiPreferencesStore(preferences_path)
        self._passwords = DocumentPasswordStore(passwords_path)

    def load_preferences(self) -> dict[str, object]:
        """Return raw persisted desktop preferences."""
        return self._preferences.load()

    def save_preferences(self, settings: dict[str, bool]) -> None:
        """Persist desktop preferences."""
        self._preferences.save(settings)

    def remember_password(self, *, path: Path, password: str) -> bool:
        """Persist a protected document password when supported."""
        return self._passwords.remember(path=path, password=password)

    def recall_password(self, path: Path) -> str | None:
        """Return a remembered password, if it remains valid."""
        return self._passwords.recall(path)

    def forget_password(self, path: Path) -> None:
        """Remove a remembered password."""
        self._passwords.forget(path)

    def move_password(self, *, source_path: Path, target_path: Path) -> None:
        """Move a remembered password after a document rename."""
        self._passwords.move(source_path=source_path, target_path=target_path)
