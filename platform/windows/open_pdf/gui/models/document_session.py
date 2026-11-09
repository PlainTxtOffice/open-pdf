"""Per-document GUI session state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from open_pdf.application.document.session import PdfDocument

if TYPE_CHECKING:
    from open_pdf.domains.document.models import PdfSearchMatch, Rectangle


@dataclass(slots=True)
class DocumentSession:
    """Store document and search state for one open desktop tab."""

    document: PdfDocument = field(default_factory=PdfDocument)
    search_matches: list[PdfSearchMatch] = field(default_factory=list)
    search_match_index: int = -1
    search_rectangles_by_page: dict[int, tuple[Rectangle, ...]] = field(
        default_factory=dict,
    )
    last_search_query: str = ""
    search_bar_visible: bool = False
    search_text: str = ""
    single_page_view_enabled: bool = False
