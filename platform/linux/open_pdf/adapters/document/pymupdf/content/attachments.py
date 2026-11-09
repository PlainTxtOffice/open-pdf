"""PyMuPDF adapters for document-level embedded text attachments."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pymupdf


def text_attachment_exists(
    document: pymupdf.Document,
    *,
    name: str,
) -> bool:
    """Return whether the document contains the named attachment."""
    return name in document.embfile_names()


def read_text_attachment(
    document: pymupdf.Document,
    *,
    name: str,
) -> str:
    """Return one UTF-8 text attachment, or an empty string if absent."""
    if not text_attachment_exists(document, name=name):
        return ""

    return document.embfile_get(name).decode("utf-8", errors="replace")


def write_text_attachment(
    document: pymupdf.Document,
    *,
    name: str,
    text: str,
    description: str,
) -> None:
    """Create, update, or remove one UTF-8 text attachment."""
    attachment_exists = text_attachment_exists(document, name=name)
    if not text:
        if attachment_exists:
            document.embfile_del(name)
        return

    encoded_text = text.encode("utf-8")
    if attachment_exists:
        # PyMuPDF 1.25.2 raises AttributeError when embfile_upd receives
        # ordinary Python bytes. Replacing the attachment is equivalent and
        # works across the supported PyMuPDF versions.
        document.embfile_del(name)

    document.embfile_add(
        name,
        encoded_text,
        filename=name,
        ufilename=name,
        desc=description,
    )
