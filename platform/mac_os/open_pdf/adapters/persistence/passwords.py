"""Remember PDF passwords exclusively in macOS Keychain."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)
_SERVICE = "Open PDF document passwords"


class PasswordBackend(Protocol):
    """Operations supplied by the native Keychain backend."""

    def get_password(self, service: str, username: str) -> str | None: ...
    def set_password(
        self, service: str, username: str, password: str,
    ) -> None: ...
    def delete_password(self, service: str, username: str) -> None: ...


def native_keychain() -> PasswordBackend | None:
    """Select the native backend directly, avoiding configurable fallbacks."""
    if sys.platform != "darwin":
        return None
    try:
        from keyring.backends.macOS import Keyring

        return Keyring()
    except Exception:
        logger.warning("Keychain is unavailable; passwords will not be saved.")
        return None


class DocumentPasswordStore:
    """Persist secrets by case-preserving resolved document path."""

    def __init__(
        self, path: Path, *, backend: PasswordBackend | None = None,
    ) -> None:
        """Keep the desktop facade's path argument without creating a file."""
        self._backend = backend if backend is not None else native_keychain()

    def remember(self, *, path: Path, password: str) -> bool:
        """Return false if access is denied or no native backend exists."""
        if self._backend is None:
            return False
        try:
            self._backend.set_password(_SERVICE, self._key(path), password)
        except Exception:
            logger.warning("Could not save a PDF password in Keychain.")
            return False
        return True

    def recall(self, path: Path) -> str | None:
        """Return a secret, preserving manual entry when Keychain is locked."""
        if self._backend is None:
            return None
        try:
            return self._backend.get_password(_SERVICE, self._key(path))
        except Exception:
            logger.warning("Could not read a PDF password from Keychain.")
            return None

    def forget(self, path: Path) -> None:
        """Remove a saved secret when Keychain permits it."""
        if self._backend is not None:
            try:
                self._backend.delete_password(_SERVICE, self._key(path))
            except Exception:
                logger.warning("Could not remove a PDF password from Keychain.")

    def move(self, *, source_path: Path, target_path: Path) -> None:
        """Keep the original entry if saving the new location fails."""
        if self._key(source_path) == self._key(target_path):
            return
        password = self.recall(source_path)
        if password is not None and self.remember(
            path=target_path, password=password,
        ):
            self.forget(source_path)

    @staticmethod
    def _key(path: Path) -> str:
        # macOS volumes may be case sensitive: never fold case here.
        return str(path.expanduser().resolve())
