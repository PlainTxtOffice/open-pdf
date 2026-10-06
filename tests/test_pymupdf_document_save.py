"""File-safety tests for the PyMuPDF save adapters."""

from pathlib import Path

import pymupdf
import pytest

from src.adapters.document.pymupdf.document import (
    save_document_copy,
    save_document_in_place,
)


def _create_pdf(path: Path, text: str) -> None:
    document = pymupdf.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), text)
        document.save(path)
    finally:
        document.close()


def _install_failing_save(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make Document.save simulate a mid-write failure at its target path."""

    def _failing_save(
        self: pymupdf.Document,
        filename: object,
        *args: object,
        **kwargs: object,
    ) -> None:
        del self, args, kwargs
        Path(str(filename)).write_bytes(b"%PDF-1.7 partial garbage")
        msg = "simulated mid-write failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(pymupdf.Document, "save", _failing_save)


def test_save_document_copy_keeps_existing_target_when_write_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source.pdf"
    target_path = tmp_path / "target.pdf"
    _create_pdf(source_path, "source content")
    _create_pdf(target_path, "precious existing target")
    original_target_bytes = target_path.read_bytes()

    document = pymupdf.open(source_path)
    try:
        _install_failing_save(monkeypatch)
        with pytest.raises(RuntimeError, match="simulated mid-write failure"):
            save_document_copy(document, target_path)
    finally:
        monkeypatch.undo()
        document.close()

    assert target_path.read_bytes() == original_target_bytes
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_document_in_place_recovers_from_non_oserror_write_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "document.pdf"
    _create_pdf(pdf_path, "original content")
    original_bytes = pdf_path.read_bytes()

    document = pymupdf.open(pdf_path)
    try:
        _install_failing_save(monkeypatch)
        with pytest.raises(RuntimeError, match="simulated mid-write failure"):
            save_document_in_place(document, pdf_path)
        monkeypatch.undo()

        assert document.is_closed is False
    finally:
        if not document.is_closed:
            document.close()

    assert pdf_path.read_bytes() == original_bytes
    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.glob("*.bak")) == []
