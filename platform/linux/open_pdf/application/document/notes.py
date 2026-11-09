"""Notes stored as a document attachment."""

from __future__ import annotations

from typing import TYPE_CHECKING

from open_pdf.adapters.document.pymupdf.content.attachments import (
    read_text_attachment,
    text_attachment_exists,
    write_text_attachment,
)
from open_pdf.domains.document.properties.notes import NotesState

if TYPE_CHECKING:
    import pymupdf

NOTES_ATTACHMENT_NAME = "notes.txt"
LEGACY_NOTES_ATTACHMENT_NAME = "notes.md"
NOTES_ATTACHMENT_DESCRIPTION = "Open PDF document notes"


class DocumentNotes:
    """Coordinate attachment persistence with pure notes state."""

    def __init__(self) -> None:
        """Start with empty notes."""
        self._state = NotesState()

    def text(self) -> str:
        """Return the current notes text."""
        return self._state.text()

    def update(self, text: str) -> bool:
        """Update notes and report whether they changed."""
        return self._state.update(text)

    def mark_saved(self) -> None:
        """Record the current text as saved after a successful PDF write."""
        self._state.mark_saved()

    def load(self, document: pymupdf.Document) -> None:
        """Seed notes text from the document's attachment, if present."""
        notes_attachment_name = NOTES_ATTACHMENT_NAME
        if not text_attachment_exists(
            document,
            name=notes_attachment_name,
        ):
            notes_attachment_name = LEGACY_NOTES_ATTACHMENT_NAME
        text = read_text_attachment(
            document,
            name=notes_attachment_name,
        )
        self._state.load(text)

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
            bool(self._state.text()) == has_current_attachment
            and not has_legacy_attachment
        )
        if self._state.is_saved() and attachment_state_is_current:
            return

        write_text_attachment(
            document,
            name=NOTES_ATTACHMENT_NAME,
            text=self._state.text(),
            description=NOTES_ATTACHMENT_DESCRIPTION,
        )
        write_text_attachment(
            document,
            name=LEGACY_NOTES_ATTACHMENT_NAME,
            text="",
            description=NOTES_ATTACHMENT_DESCRIPTION,
        )
