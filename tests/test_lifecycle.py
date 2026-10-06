"""Tests for document lifecycle predicates."""

from pathlib import Path

from src.domains.document.lifecycle import references_same_file


def test_same_existing_file_compares_equal(tmp_path: Path) -> None:
    target = tmp_path / "document.pdf"
    target.write_bytes(b"content")

    assert references_same_file(target, target) is True


def test_different_existing_files_compare_unequal(tmp_path: Path) -> None:
    first = tmp_path / "one.pdf"
    second = tmp_path / "two.pdf"
    first.write_bytes(b"content")
    second.write_bytes(b"content")

    assert references_same_file(first, second) is False
