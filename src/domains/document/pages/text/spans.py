"""Match a page selection to the text span it covers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.domains.document.models import PdfTextSpan

type Rectangle = tuple[float, float, float, float]


def _overlap_area(first: Rectangle, second: Rectangle) -> float:
    """Return the area shared by two PDF-space rectangles."""
    ax0, ay0, ax1, ay1 = first
    bx0, by0, bx1, by1 = second
    width = min(max(ax0, ax1), max(bx0, bx1)) - max(
        min(ax0, ax1), min(bx0, bx1)
    )
    height = min(max(ay0, ay1), max(by0, by1)) - max(
        min(ay0, ay1),
        min(by0, by1),
    )
    if width <= 0 or height <= 0:
        return 0.0

    return width * height


def span_for_rectangles(
    spans: Sequence[PdfTextSpan],
    rectangles: Sequence[Rectangle],
) -> PdfTextSpan | None:
    """Return the span the selection covers most, or None when it covers none.

    - Ties go to the earlier span, so a selection spanning two equal
      candidates resolves in reading order.
    """
    best_span: PdfTextSpan | None = None
    best_area = 0.0
    for span in spans:
        area = sum(
            _overlap_area(span.bounds, rectangle) for rectangle in rectangles
        )
        if area > best_area:
            best_span = span
            best_area = area

    return best_span
