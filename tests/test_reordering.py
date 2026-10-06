"""Tests for pure page-index transformations."""

import pytest

from src.domains.document.pages.reordering import (
    dirty_pages_after_delete,
    dirty_pages_after_insert,
    dirty_pages_after_move,
    page_index_after_move,
    validate_page_index,
)


def test_delete_reindexes_existing_and_shifted_dirty_pages() -> None:
    assert dirty_pages_after_delete(
        {0, 2, 4},
        deleted_index=2,
        remaining_page_count=4,
    ) == {0, 2, 3}


def test_move_forward_reindexes_affected_pages() -> None:
    assert page_index_after_move(1, page_index=1, destination_index=3) == 3
    assert page_index_after_move(2, page_index=1, destination_index=3) == 1


def test_move_backward_reindexes_affected_pages() -> None:
    assert page_index_after_move(3, page_index=3, destination_index=1) == 1
    assert page_index_after_move(2, page_index=3, destination_index=1) == 3


def test_move_marks_whole_affected_range_dirty() -> None:
    assert dirty_pages_after_move(
        {0, 4},
        page_index=1,
        destination_index=3,
    ) == {0, 1, 2, 3, 4}


def test_page_index_beyond_document_is_rejected() -> None:
    with pytest.raises(ValueError, match="out of range"):
        validate_page_index(7, page_count=3)


def test_page_index_within_document_is_returned() -> None:
    assert validate_page_index(2, page_count=3) == 2


def test_dirty_pages_shift_up_after_an_insert() -> None:
    assert dirty_pages_after_insert(
        {0, 2},
        inserted_index=1,
        page_count=4,
    ) == {0, 1, 2, 3}


def test_dirty_pages_before_an_insert_keep_their_index() -> None:
    assert dirty_pages_after_insert(
        {0},
        inserted_index=3,
        page_count=4,
    ) == {0, 3}
