"""PyMuPDF lifecycle operations."""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Final
from uuid import uuid4

import pymupdf

from open_pdf.domains.document.errors import (
    IncorrectPasswordError,
    PasswordRequiredError,
)

if TYPE_CHECKING:
    from pathlib import Path


_PDF_ENCRYPT_KEEP: Final = int(getattr(pymupdf, "PDF_ENCRYPT_KEEP", 0))


def _temporary_pdf_path(path: Path) -> Path:
    while True:
        temporary_path = path.with_name(
            f".{path.stem}.{uuid4().hex}{path.suffix}.tmp",
        )
        if not temporary_path.exists():
            return temporary_path


def _backup_pdf_path(path: Path) -> Path:
    while True:
        backup_path = path.with_name(
            f".{path.stem}.{uuid4().hex}{path.suffix}.bak",
        )
        if not backup_path.exists():
            return backup_path


def open_document(
    path: Path,
    *,
    password: str | None = None,
) -> pymupdf.Document:
    """Open a PDF document from disk."""
    document = pymupdf.open(path)
    if not document.needs_pass:
        return document

    attempted_password = "" if password is None else password
    if document.authenticate(attempted_password) > 0:
        return document

    document.close()
    if password is not None:
        msg = "The provided PDF password is incorrect."
        raise IncorrectPasswordError(msg)

    msg = "This PDF is password-protected and requires a password to open."
    raise PasswordRequiredError(msg)


def close_document(document: pymupdf.Document | None) -> None:
    """Close a document when one is open."""
    if document is not None:
        document.close()


def can_save_incrementally(document: pymupdf.Document) -> bool:
    """Return whether the document supports in-place incremental save."""
    return bool(document.can_save_incrementally())


def save_document(document: pymupdf.Document) -> None:
    """Write document changes back to the opened file."""
    document.saveIncr()


def save_document_copy(document: pymupdf.Document, path: Path) -> None:
    """Write document changes to a target path via an atomic replace."""
    temporary_path = _temporary_pdf_path(path)
    try:
        document.save(temporary_path, encryption=_PDF_ENCRYPT_KEEP)
        temporary_path.replace(path)
    except Exception:
        with suppress(OSError):
            temporary_path.unlink(missing_ok=True)
        raise


def save_document_in_place(document: pymupdf.Document, path: Path) -> None:
    """Write document changes back to the opened file via a safe replace."""
    temporary_path = _temporary_pdf_path(path)
    backup_path = _backup_pdf_path(path)
    source_backed_up = False
    try:
        document.save(temporary_path, encryption=_PDF_ENCRYPT_KEEP)
        document.close()
        path.replace(backup_path)
        source_backed_up = True
        temporary_path.replace(path)
    except Exception:
        with suppress(OSError):
            temporary_path.unlink(missing_ok=True)
        if source_backed_up and backup_path.exists() and not path.exists():
            backup_path.replace(path)
        raise
    else:
        backup_path.unlink(missing_ok=True)


def load_document_page(
    document: pymupdf.Document, page_index: int
) -> pymupdf.Page:
    """Load an engine page for an application workflow."""
    return document.load_page(page_index)
