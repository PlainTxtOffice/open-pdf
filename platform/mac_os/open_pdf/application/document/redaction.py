"""Rectangle redaction for a single page."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from open_pdf.domains.document.pages.reordering import validate_page_index

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
    validate_page_index(page_index, page_count=document.page_count)

    if not rectangles:
        return False

    return apply_redactions(document, page_index, rectangles)
