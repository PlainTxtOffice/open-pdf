"""In-memory view state for the active PDF document."""

from __future__ import annotations

from dataclasses import dataclass

MIN_ZOOM = 0.25
MAX_ZOOM = 4.0
ZOOM_STEP = 0.25


@dataclass(slots=True)
class PdfViewState:
    """Tracks the page position and zoom level for the active document."""

    page_count: int = 0
    current_page_index: int = 0
    zoom: float = 1.0

    def reset(self, *, page_count: int) -> None:
        """Reset the view state for a newly loaded document."""
        self.page_count = max(page_count, 0)
        self.current_page_index = 0
        self.zoom = 1.0

    def has_pages(self) -> bool:
        """Return whether the active document contains any pages."""
        return self.page_count > 0

    def set_page(self, page_index: int) -> None:
        """Update the current page index.

        - Clamps the requested index to the valid page range.
        - Defaults to the first page if the document has no pages.
        """
        if not self.has_pages():
            self.current_page_index = 0
            return

        self.current_page_index = min(
            max(page_index, 0),
            self.page_count - 1,
        )

    def next_page(self) -> None:
        """Advance to the next page if one exists."""
        self.set_page(self.current_page_index + 1)

    def previous_page(self) -> None:
        """Return to the previous page if one exists."""
        self.set_page(self.current_page_index - 1)

    def set_zoom(self, zoom: float) -> None:
        """Update the current zoom level.

        - Clamps the requested zoom to the allowed minimum and maximum values.
        """
        self.zoom = min(max(zoom, MIN_ZOOM), MAX_ZOOM)

    def zoom_in(self) -> None:
        """Increase the current zoom level by one step."""
        self.set_zoom(self.zoom + ZOOM_STEP)

    def zoom_out(self) -> None:
        """Decrease the current zoom level by one step."""
        self.set_zoom(self.zoom - ZOOM_STEP)

    def page_label(self) -> str:
        """Return a formatted string representing the current page position."""
        if not self.has_pages():
            return "Page 0 / 0"

        return f"Page {self.current_page_index + 1} / {self.page_count}"
