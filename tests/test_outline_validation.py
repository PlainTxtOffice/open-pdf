"""Tests for outline validation."""

import pytest

from src.domains.document.properties.outlines import (
    validate_bookmark_title,
    validate_outline_index,
)


def test_blank_title_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_bookmark_title("   ")


def test_title_is_stripped() -> None:
    assert validate_bookmark_title("  chapter one  ") == "chapter one"


def test_outline_index_beyond_entries_is_rejected() -> None:
    with pytest.raises(ValueError, match="out of range"):
        validate_outline_index(4, entry_count=2)
