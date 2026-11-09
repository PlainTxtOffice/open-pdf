"""Prepare Linux user storage before loading desktop consumers."""

from open_pdf.config.path_handler import CACHE_DIR, CONFIG_DIR, LOGS_DIR


def prepare_storage() -> None:
    """Create the app's XDG directories without migrating other platforms."""
    for directory in (CONFIG_DIR, CACHE_DIR, LOGS_DIR):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
