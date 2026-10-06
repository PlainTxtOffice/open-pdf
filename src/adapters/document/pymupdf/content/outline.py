"""Adapters for PyMuPDF outline extraction."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domains.document.models import PdfOutlineItem
from src.domains.document.properties.outlines import (
    normalize_outline_page_index,
)

if TYPE_CHECKING:
    import pymupdf


_OUTLINE_ENTRY_MIN_LENGTH = 3
_OUTLINE_DESTINATION_INDEX = 3


def outline_items(document: pymupdf.Document) -> list[PdfOutlineItem]:
    """Return normalized outline entries for a document."""
    items: list[PdfOutlineItem] = []

    for toc_index, entry in enumerate(document.get_toc(simple=False)):
        if len(entry) < _OUTLINE_ENTRY_MIN_LENGTH:
            continue

        level = entry[0]
        title = entry[1]
        destination_page = entry[2]
        if not isinstance(level, int) or not isinstance(title, str):
            continue

        page_index = normalize_outline_page_index(
            page_value=destination_page,
            destination=(
                entry[_OUTLINE_DESTINATION_INDEX]
                if len(entry) > _OUTLINE_DESTINATION_INDEX
                else None
            ),
        )
        if page_index is None:
            continue

        items.append(
            PdfOutlineItem(
                toc_index=toc_index,
                level=level,
                title=title,
                page_index=page_index,
            ),
        )

    return items


def append_outline_item(
    document: pymupdf.Document,
    *,
    title: str,
    page_index: int,
    level: int = 1,
) -> None:
    """Append one outline entry to the document table of contents."""
    toc = document.get_toc()
    toc.append([level, title, page_index + 1])
    document.set_toc(toc)


def rename_outline_item(
    document: pymupdf.Document,
    *,
    toc_index: int,
    title: str,
) -> None:
    """Rename one outline entry in the document table of contents."""
    toc = document.get_toc(simple=False)
    toc[toc_index][1] = title
    document.set_toc(toc)


def delete_outline_item(
    document: pymupdf.Document,
    *,
    toc_index: int,
) -> None:
    """Delete one outline entry and its nested descendants."""
    toc = document.get_toc(simple=False)
    selected_level = toc[toc_index][0]
    delete_end = toc_index + 1
    while delete_end < len(toc) and toc[delete_end][0] > selected_level:
        delete_end += 1

    del toc[toc_index:delete_end]
    document.set_toc(toc)
