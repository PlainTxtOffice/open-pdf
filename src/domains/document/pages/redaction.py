"""Rectangle redaction for a single page."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pymupdf


class RedactionApplier(Protocol):
    """Apply PDF-space rectangles to one page as opaque redactions."""

    def __call__(
        self,
        document: pymupdf.Document,
        page_index: int,
        rectangles: Sequence[tuple[float, float, float, float]],
    ) -> bool:
        """Return whether at least one non-empty rectangle was applied."""
        ...


def redact_rectangles(
    document: pymupdf.Document,
    page_index: int,
    rectangles: Sequence[tuple[float, float, float, float]],
    *,
    apply_redactions: RedactionApplier,
) -> bool:
    """Redact rectangles on one page and report whether anything changed.

    Raises:
        ValueError: The page index is outside the document.

    """
    if not 0 <= page_index < document.page_count:
        msg = f"Page index {page_index} is out of range."
        raise ValueError(msg)

    if not rectangles:
        return False

    return apply_redactions(document, page_index, rectangles)
