"""Prepare native writable storage before importing desktop consumers."""

from open_pdf.config import path_handler as paths


def prepare_storage() -> None:
    """Create per-user runtime folders; never write to the app bundle."""
    for directory in (paths.DATA_DIR, paths.CACHE_DIR, paths.LOGS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
