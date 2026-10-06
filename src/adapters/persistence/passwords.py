"""Protected local persistence for remembered PDF passwords."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from src.config.protected_data import protect_string, unprotect_string

if TYPE_CHECKING:
    from pathlib import Path


logger = logging.getLogger(__name__)


class DocumentPasswordStore:
    """Persist protected document passwords by normalized path."""

    def __init__(self, path: Path) -> None:
        """Load any previously stored passwords from `path`."""
        self._path = path
        self._passwords = self._load()

    def remember(self, *, path: Path, password: str) -> bool:
        """Protect and persist one password, returning whether supported."""
        protected_password = protect_string(password)
        if protected_password is None:
            return False
        self._passwords[self._key(path)] = protected_password
        self._save()
        return True

    def recall(self, path: Path) -> str | None:
        """Return one remembered password, removing invalid values."""
        protected_password = self._passwords.get(self._key(path))
        if protected_password is None:
            return None
        password = unprotect_string(protected_password)
        if password is not None:
            return password
        self.forget(path)
        return None

    def forget(self, path: Path) -> None:
        """Remove one remembered password."""
        if self._passwords.pop(self._key(path), None) is not None:
            self._save()

    def move(self, *, source_path: Path, target_path: Path) -> None:
        """Move one password entry to a renamed document path."""
        source_key = self._key(source_path)
        target_key = self._key(target_path)
        if source_key == target_key:
            return
        protected_password = self._passwords.pop(source_key, None)
        if protected_password is None:
            return
        self._passwords[target_key] = protected_password
        self._save()

    @staticmethod
    def _key(path: Path) -> str:
        try:
            normalized_path = path.resolve()
        except OSError:
            normalized_path = path.absolute()
        return str(normalized_path).casefold()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"passwords": self._passwords}, indent=2),
            encoding="utf-8",
        )

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            raw_passwords = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception(
                "Could not read document passwords from %s",
                self._path,
            )
            return {}
        if not isinstance(raw_passwords, dict):
            return {}
        passwords = raw_passwords.get("passwords")
        if not isinstance(passwords, dict):
            return {}
        return {
            key: value
            for key, value in passwords.items()
            if isinstance(key, str) and isinstance(value, str)
        }
