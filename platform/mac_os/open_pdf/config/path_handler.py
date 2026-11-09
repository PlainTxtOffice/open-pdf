"""Read-only bundle assets and native per-user macOS storage paths."""

from pathlib import Path

APP_DATA_DIR_NAME = "Open PDF"
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
STORAGE_MODE = "macos-user"


def storage_paths(home: Path) -> tuple[Path, Path, Path]:
    """Resolve data, cache, and log locations without filesystem changes."""
    library = home / "Library"
    return (
        library / "Application Support" / APP_DATA_DIR_NAME,
        library / "Caches" / APP_DATA_DIR_NAME,
        library / "Logs" / APP_DATA_DIR_NAME,
    )


DATA_DIR, CACHE_DIR, LOGS_DIR = storage_paths(Path.home())
ROOT_DIR = DATA_DIR
