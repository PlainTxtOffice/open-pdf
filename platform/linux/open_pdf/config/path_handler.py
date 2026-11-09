"""Side-effect-free Linux paths for source and packaged launches."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

APP_DATA_DIR_NAME = "open-pdf"
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
STORAGE_MODE = "xdg"


def xdg_directory(
    environ: Mapping[str, str], name: str, fallback: Path,
) -> Path:
    """Use an absolute XDG override, otherwise the home-relative default."""
    value = environ.get(name, "")
    root = Path(value) if value and Path(value).is_absolute() else fallback
    return root / APP_DATA_DIR_NAME


CONFIG_DIR = xdg_directory(
    os.environ, "XDG_CONFIG_HOME", Path.home() / ".config",
)
CACHE_DIR = xdg_directory(
    os.environ, "XDG_CACHE_HOME", Path.home() / ".cache",
)
ROOT_DIR = xdg_directory(
    os.environ, "XDG_STATE_HOME", Path.home() / ".local" / "state",
)
LOGS_DIR = ROOT_DIR / "logs"
