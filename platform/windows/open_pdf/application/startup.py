"""Prepare runtime storage before loading desktop consumers."""

from open_pdf.adapters.runtime.storage import (
    is_writable_dir,
    migrate_legacy_folder,
)
from open_pdf.config import path_handler as paths


def prepare_storage() -> None:
    """Migrate existing folders, then select the writable storage root.

    Call before importing logging or GUI modules that capture path constants.
    Development never migrates user folders.
    """
    if paths.IS_COMPILED:
        migrate_legacy_folder(
            paths.USER_DATA_DIR.with_name(paths.LEGACY_APP_DATA_DIR_NAME),
            paths.USER_DATA_DIR,
        )
        if paths.IS_PORTABLE:
            migrate_legacy_folder(
                paths.EXE_DIR / paths.LEGACY_PORTABLE_DATA_DIR_NAME,
                paths.EXE_DIR / paths.PORTABLE_DATA_DIR_NAME,
            )
    mode, root = paths.resolve_storage(
        is_compiled=paths.IS_COMPILED,
        is_portable=paths.IS_PORTABLE,
        exe_dir=paths.EXE_DIR,
        user_data_dir=paths.USER_DATA_DIR,
        is_writable=is_writable_dir,
    )
    paths.configure_storage(mode, root)
