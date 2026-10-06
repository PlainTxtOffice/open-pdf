"""Pure matching helpers for OCR-derived PDF words."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pymupdf

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.domains.document.models import PdfPageWord


def match_rectangles(
    words: Sequence[PdfPageWord],
    query: str,
) -> tuple[pymupdf.Rect, ...]:
    """Return word rectangles matching a case-insensitive query."""
    search_terms = [term.casefold() for term in query.split() if term]
    if not search_terms:
        return ()

    lowered_words = [word[4].casefold() for word in words]
    if len(search_terms) == 1:
        target = search_terms[0]
        return tuple(
            _bounding_rect((word,))
            for word, lowered_word in zip(words, lowered_words, strict=False)
            if target in lowered_word
        )

    rectangles: list[pymupdf.Rect] = []
    term_count = len(search_terms)
    for start_index in range(len(words) - term_count + 1):
        end_index = start_index + term_count
        if lowered_words[start_index:end_index] == search_terms:
            rectangles.append(_bounding_rect(words[start_index:end_index]))
    return tuple(rectangles)


def _bounding_rect(words: Sequence[PdfPageWord]) -> pymupdf.Rect:
    return pymupdf.Rect(
        min(word[0] for word in words),
        min(word[1] for word in words),
        max(word[2] for word in words),
        max(word[3] for word in words),
    )
