"""JSON persistence adapter for desktop UI preferences."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


logger = logging.getLogger(__name__)


class UiPreferencesStore:
    """Read and write desktop preferences as one JSON object."""

    def __init__(self, path: Path) -> None:
        """Initialize the preferences store with a file path."""
        self._path = path

    def load(self) -> dict[str, object]:
        """Return persisted preferences, falling back to an empty object."""
        if not self._path.exists():
            return {}

        try:
            raw_settings = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception(
                "Could not read UI preferences from %s",
                self._path,
            )
            return {}

        return raw_settings if isinstance(raw_settings, dict) else {}

    def save(self, settings: dict[str, bool]) -> None:
        """Persist desktop preferences as UTF-8 JSON."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(settings, indent=2),
            encoding="utf-8",
        )
