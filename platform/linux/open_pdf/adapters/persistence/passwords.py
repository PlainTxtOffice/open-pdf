"""Remember PDF passwords exclusively in the desktop Secret Service."""

from __future__ import annotations

import logging
from pathlib import Path

from keyring.backends.SecretService import Keyring
from keyring.errors import KeyringError

_KEYRING_ERRORS: tuple[type[Exception], ...] = (
    KeyringError, OSError, RuntimeError,
)
try:
    from secretstorage.exceptions import SecretStorageException

    _KEYRING_ERRORS += (SecretStorageException,)
except ImportError:
    # Keyring.priority reports an unavailable backend on non-Linux hosts.
    pass

logger = logging.getLogger(__name__)
_SERVICE = "com.plaintxtoffice.OpenPDF"


class DocumentPasswordStore:
    """Store credentials in the user's keyring, never in app files."""

    def __init__(self) -> None:
        """Select Secret Service explicitly, bypassing fallback backends."""
        self._backend: Keyring | None = None
        try:
            if Keyring.priority > 0:
                self._backend = Keyring()
        except _KEYRING_ERRORS:
            pass

    @staticmethod
    def _key(path: Path) -> str:
        """Preserve Linux filename case in credential identifiers."""
        return str(path.expanduser().resolve())

    def remember(self, *, path: Path, password: str) -> bool:
        """Return false when the desktop keyring cannot save the password."""
        if self._backend is None:
            return False
        try:
            self._backend.set_password(_SERVICE, self._key(path), password)
        except _KEYRING_ERRORS:
            logger.warning("Desktop keyring unavailable; password not saved")
            return False
        return True

    def recall(self, path: Path) -> str | None:
        """Return a saved password, or let the UI request one manually."""
        if self._backend is None:
            return None
        try:
            return self._backend.get_password(_SERVICE, self._key(path))
        except _KEYRING_ERRORS:
            return None

    def forget(self, path: Path) -> None:
        """Remove a saved password when the keyring is available."""
        if self._backend is None:
            return
        try:
            self._backend.delete_password(_SERVICE, self._key(path))
        except _KEYRING_ERRORS:
            logger.warning("Desktop keyring unavailable; password not removed")

    def move(self, *, source_path: Path, target_path: Path) -> None:
        """Keep the old entry unless saving the renamed path succeeds."""
        if self._key(source_path) == self._key(target_path):
            return
        password = self.recall(source_path)
        if password is not None and self.remember(
            path=target_path, password=password,
        ):
            self.forget(source_path)
