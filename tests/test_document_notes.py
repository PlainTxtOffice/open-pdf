"""Tests for the document notes collaborator."""

import pymupdf
import pytest

from src.domains.document.properties import notes as notes_module
from src.domains.document.properties.notes import (
    LEGACY_NOTES_ATTACHMENT_NAME,
    NOTES_ATTACHMENT_NAME,
    DocumentNotes,
)


def test_update_returns_true_when_text_changes() -> None:
    notes = DocumentNotes()
    assert notes.update("hello") is True


def test_update_returns_false_when_text_is_unchanged() -> None:
    notes = DocumentNotes()
    notes.update("hello")
    assert notes.update("hello") is False


def test_text_reflects_current_value() -> None:
    notes = DocumentNotes()
    notes.update("hello")
    assert notes.text() == "hello"


def test_text_starts_empty() -> None:
    notes = DocumentNotes()
    assert notes.text() == ""


def test_load_seeds_text_from_current_attachment() -> None:
    document = pymupdf.open()
    document.embfile_add(NOTES_ATTACHMENT_NAME, b"stored notes")

    notes = DocumentNotes()
    notes.load(document)

    assert notes.text() == "stored notes"
    document.close()


def test_load_falls_back_to_legacy_attachment() -> None:
    document = pymupdf.open()
    document.embfile_add(LEGACY_NOTES_ATTACHMENT_NAME, b"legacy notes")

    notes = DocumentNotes()
    notes.load(document)

    assert notes.text() == "legacy notes"
    document.close()


def test_flush_writes_current_attachment() -> None:
    document = pymupdf.open()

    notes = DocumentNotes()
    notes.update("fresh notes")
    notes.flush(document)

    assert document.embfile_get(NOTES_ATTACHMENT_NAME) == b"fresh notes"
    document.close()


def test_flush_skips_write_when_unchanged_and_current() -> None:
    document = pymupdf.open()

    notes = DocumentNotes()
    notes.load(document)
    notes.flush(document)

    assert NOTES_ATTACHMENT_NAME not in document.embfile_names()
    document.close()


def test_mark_saved_prevents_redundant_rewrite_on_next_flush(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = pymupdf.open()

    notes = DocumentNotes()
    notes.update("first save")
    notes.flush(document)

    original_write = notes_module.write_text_attachment
    write_calls: list[None] = []

    def spy_write(*args: object, **kwargs: object) -> None:
        write_calls.append(None)
        original_write(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(notes_module, "write_text_attachment", spy_write)

    # Without mark_saved(), the saved text is still stale, so flush()
    # rewrites the (already correct) attachment again.
    notes.flush(document)
    assert write_calls

    write_calls.clear()
    notes.mark_saved()
    notes.flush(document)

    assert write_calls == []
    document.close()
