"""Notes stored as a document attachment."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.adapters.document.pymupdf.content.attachments import (
    read_text_attachment,
    text_attachment_exists,
    write_text_attachment,
)

if TYPE_CHECKING:
    import pymupdf

NOTES_ATTACHMENT_NAME = "notes.txt"
LEGACY_NOTES_ATTACHMENT_NAME = "notes.md"
NOTES_ATTACHMENT_DESCRIPTION = "Open PDF document notes"


class DocumentNotes:
    """Own the plain-text notes attachment for the active document."""

    def __init__(self) -> None:
        """Initialize with no stored notes."""
        self._notes_text = ""
        self._saved_notes_text = ""

    def text(self) -> str:
        """Return the current notes text."""
        return self._notes_text

    def update(self, text: str) -> bool:
        """Replace the notes text and report whether it changed."""
        if self._notes_text == text:
            return False

        self._notes_text = text
        return True

    def mark_saved(self) -> None:
        """Record the current text as the last text written to disk."""
        self._saved_notes_text = self._notes_text

    def load(self, document: pymupdf.Document) -> None:
        """Seed notes text from the document's attachment, if present."""
        notes_attachment_name = NOTES_ATTACHMENT_NAME
        if not text_attachment_exists(
            document,
            name=notes_attachment_name,
        ):
            notes_attachment_name = LEGACY_NOTES_ATTACHMENT_NAME
        self._notes_text = read_text_attachment(
            document,
            name=notes_attachment_name,
        )
        self._saved_notes_text = self._notes_text

    def flush(self, document: pymupdf.Document) -> None:
        """Apply pending note text to the in-memory PDF before saving."""
        has_current_attachment = text_attachment_exists(
            document,
            name=NOTES_ATTACHMENT_NAME,
        )
        has_legacy_attachment = text_attachment_exists(
            document,
            name=LEGACY_NOTES_ATTACHMENT_NAME,
        )
        attachment_state_is_current = (
            bool(self._notes_text) == has_current_attachment
            and not has_legacy_attachment
        )
        if (
            self._notes_text == self._saved_notes_text
            and attachment_state_is_current
        ):
            return

        write_text_attachment(
            document,
            name=NOTES_ATTACHMENT_NAME,
            text=self._notes_text,
            description=NOTES_ATTACHMENT_DESCRIPTION,
        )
        write_text_attachment(
            document,
            name=LEGACY_NOTES_ATTACHMENT_NAME,
            text="",
            description=NOTES_ATTACHMENT_DESCRIPTION,
        )
