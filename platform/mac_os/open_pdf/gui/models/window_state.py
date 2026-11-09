"""Grouped mutable state owned by the main viewer window."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_pdf.domains.document.models import PdfSearchMatch, Rectangle


@dataclass(slots=True)
class SearchState:
    """Live search results for the active document."""

    matches: list[PdfSearchMatch] = field(default_factory=list)
    match_index: int = -1
    rectangles_by_page: dict[int, tuple[Rectangle, ...]] = field(
        default_factory=dict,
    )
    last_query: str = ""


@dataclass(slots=True)
class OcrState:
    """Live OCR progress for the active document tab."""

    active: bool = False
    completed_pages: int = 0
    total_pages: int = 0


@dataclass(slots=True)
class SyncGuards:
    """Reentrancy guards that suppress widget feedback loops."""

    switching_document_tabs: bool = False
    page_selector: bool = False
    thumbnail_list: bool = False
    scroll_position: bool = False
    notes_text: bool = False


@dataclass(slots=True)
class RenderGenerations:
    """Tokens used to discard stale asynchronous results."""

    render: int = 0
    thumbnail: int = 0
    search: int = 0
    ocr: int = 0
    counter: int = 0


@dataclass(slots=True)
class PaneSettings:
    """Persisted visibility and layout choices for secondary panes."""

    bookmarks_visible: bool = True
    thumbnails_visible: bool = True
    text_visible: bool = True
    notes_visible: bool = True
    text_selection_mode: bool = True
    thumbnails_on_left: bool = False

    @classmethod
    def from_dict(cls, raw: object) -> PaneSettings:
        """Build settings from JSON, ignoring unknown or invalid keys."""
        settings = cls()
        if not isinstance(raw, dict):
            return settings

        for setting_field in fields(cls):
            value = raw.get(setting_field.name)
            if isinstance(value, bool):
                setattr(settings, setting_field.name, value)
        return settings

    def as_dict(self) -> dict[str, bool]:
        """Return settings as a JSON-serializable mapping."""
        return {
            setting_field.name: getattr(self, setting_field.name)
            for setting_field in fields(self)
        }
