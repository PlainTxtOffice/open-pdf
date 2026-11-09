"""Pure page-index transformations for document editing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet


def dirty_pages_after_delete(
    dirty_pages: AbstractSet[int],
    *,
    deleted_index: int,
    remaining_page_count: int,
) -> set[int]:
    """Return dirty indexes after removing one page."""
    reindexed_pages = {
        dirty_index - 1 if dirty_index > deleted_index else dirty_index
        for dirty_index in dirty_pages
        if dirty_index != deleted_index
    }
    shifted_pages = set(range(deleted_index, remaining_page_count))
    return reindexed_pages | shifted_pages


def dirty_pages_after_insert(
    dirty_pages: AbstractSet[int],
    *,
    inserted_index: int,
    page_count: int,
) -> set[int]:
    """Return dirty indexes after inserting one page.

    - Pages at or after the insertion point shift up by one, and every
      index from the insertion point onward needs re-rendering.
    """
    reindexed_pages = {
        dirty_index + 1 if dirty_index >= inserted_index else dirty_index
        for dirty_index in dirty_pages
    }
    shifted_pages = set(range(inserted_index, page_count))
    return reindexed_pages | shifted_pages


def dirty_pages_after_move(
    dirty_pages: AbstractSet[int],
    *,
    page_index: int,
    destination_index: int,
) -> set[int]:
    """Return dirty indexes after moving one page."""
    reindexed_pages = {
        page_index_after_move(
            dirty_index,
            page_index=page_index,
            destination_index=destination_index,
        )
        for dirty_index in dirty_pages
    }
    first_dirty_index = min(page_index, destination_index)
    last_dirty_index = max(page_index, destination_index)
    return reindexed_pages | set(
        range(first_dirty_index, last_dirty_index + 1),
    )


def page_index_after_move(
    existing_index: int,
    *,
    page_index: int,
    destination_index: int,
) -> int:
    """Return where an existing page index lands after a move."""
    if existing_index == page_index:
        return destination_index
    if page_index < destination_index:
        if page_index < existing_index <= destination_index:
            return existing_index - 1
        return existing_index
    if destination_index <= existing_index < page_index:
        return existing_index + 1
    return existing_index


def validate_page_index(page_index: int, *, page_count: int) -> int:
    """Return the page index after bounds checking.

    Raises:
        ValueError: The index is outside the document.

    """
    if not 0 <= page_index < page_count:
        msg = f"Page index {page_index} is out of range."
        raise ValueError(msg)

    return page_index


def page_index_after_delete(
    current_index: int, *, deleted_index: int, remaining_page_count: int
) -> int:
    """Keep the same page selected when possible after a deletion."""
    if current_index > deleted_index:
        return current_index - 1
    return min(current_index, max(remaining_page_count - 1, 0))


def blank_page_position(at_index: int, *, page_count: int) -> tuple[int, int]:
    """Return the insertion position and neighboring page to copy.

    The neighbor is -1 for an empty document, where the caller uses Letter size.
    """
    insert_index = min(max(at_index, 0), page_count)
    return insert_index, min(insert_index, page_count - 1)
