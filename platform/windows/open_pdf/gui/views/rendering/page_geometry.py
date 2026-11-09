"""Page geometry helpers for the scrollable document view."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout

    from open_pdf.application.document.session import PdfDocument


_DEFAULT_PAGE_BORDER_STYLE = (
    "background: white;border: 1px solid #d0d0d0;padding: 4px;"
)
_CURRENT_PAGE_BORDER_STYLE = (
    "background: white;border: 3px solid #9aa0a6;padding: 4px;"
)


class _PageGeometryHost(Protocol):
    """Describe the main-window API required by PageGeometryMixin."""

    _document: PdfDocument
    _page_labels: list[QLabel]
    _visible_page_indexes: list[int]
    _document_scroll_area: QScrollArea
    _document_layout: QVBoxLayout
    _page_top_offsets: list[int]
    _page_bottom_offsets: list[int]
    _highlighted_page_index: int | None

    def _geometry_cache_is_ready(self) -> bool: ...

    def _visible_label_range(self) -> tuple[int, int]: ...

    def _label_center(self, label_index: int) -> float: ...

    def _label_index_for_page(
        self,
        page_index: int | None,
    ) -> int | None: ...


class PageGeometryMixin:
    """Compute visible page ranges and current-page highlighting."""

    if TYPE_CHECKING:
        # Declared so the type matches _PageGeometryHost rather than
        # being inferred as int from the assignment below.
        _highlighted_page_index: int | None

    def _rebuild_page_geometry_cache(self: _PageGeometryHost) -> None:
        """Recompute cached vertical offsets for every page label.

        - Must be called after any change that resizes page labels (open,
          zoom, rotate) so geometry queries stay in sync.
        """
        margins = self._document_layout.contentsMargins()
        spacing = self._document_layout.spacing()

        tops: list[int] = []
        bottoms: list[int] = []
        cursor = margins.top()
        for page_label in self._page_labels:
            tops.append(cursor)
            cursor += page_label.height()
            bottoms.append(cursor)
            cursor += spacing

        self._page_top_offsets = tops
        self._page_bottom_offsets = bottoms

    def _clear_page_geometry_cache(self: _PageGeometryHost) -> None:
        """Drop cached page offsets when no document is loaded."""
        self._page_top_offsets = []
        self._page_bottom_offsets = []

    def _visible_page_index(self: _PageGeometryHost) -> int | None:
        if not self._page_labels or not self._geometry_cache_is_ready():
            return None

        scroll_bar = self._document_scroll_area.verticalScrollBar()
        viewport_height = self._document_scroll_area.viewport().height()
        viewport_center = scroll_bar.value() + (viewport_height // 2)

        candidate_label_index = max(
            bisect_right(self._page_top_offsets, viewport_center) - 1,
            0,
        )
        next_label_index = candidate_label_index + 1
        if next_label_index >= len(self._page_labels):
            return self._visible_page_indexes[candidate_label_index]

        candidate_center = self._label_center(candidate_label_index)
        next_center = self._label_center(next_label_index)
        if abs(next_center - viewport_center) < abs(
            candidate_center - viewport_center,
        ):
            return self._visible_page_indexes[next_label_index]
        return self._visible_page_indexes[candidate_label_index]

    def _apply_default_page_border(
        self: _PageGeometryHost,
        page_label: QLabel,
    ) -> None:
        page_label.setStyleSheet(_DEFAULT_PAGE_BORDER_STYLE)

    def _update_current_page_highlight(self: _PageGeometryHost) -> None:
        current_page_index = self._document.state.current_page_index
        previous_index = self._highlighted_page_index
        if previous_index == current_page_index:
            return

        previous_label_index = self._label_index_for_page(previous_index)
        if previous_label_index is not None:
            self._page_labels[previous_label_index].setStyleSheet(
                _DEFAULT_PAGE_BORDER_STYLE,
            )

        current_label_index = self._label_index_for_page(current_page_index)
        if current_label_index is not None:
            self._page_labels[current_label_index].setStyleSheet(
                _CURRENT_PAGE_BORDER_STYLE,
            )
            self._highlighted_page_index = current_page_index
        else:
            self._highlighted_page_index = None

    def _visible_page_range(self: _PageGeometryHost) -> tuple[int, int]:
        """Map the visible label range to document page indexes."""
        if not self._page_labels or not self._geometry_cache_is_ready():
            return 0, 0

        first_visible_label, last_visible_label = self._visible_label_range()
        return (
            self._visible_page_indexes[first_visible_label],
            self._visible_page_indexes[last_visible_label],
        )

    def _visible_label_range(self: _PageGeometryHost) -> tuple[int, int]:
        """Return inclusive visible label indexes, or zeros without geometry."""
        if not self._page_labels or not self._geometry_cache_is_ready():
            return 0, 0

        scroll_bar = self._document_scroll_area.verticalScrollBar()
        viewport_top = scroll_bar.value()
        viewport_bottom = (
            viewport_top + self._document_scroll_area.viewport().height()
        )

        last_index = len(self._page_labels) - 1
        first_visible = min(
            bisect_left(self._page_bottom_offsets, viewport_top),
            last_index,
        )
        last_visible = max(
            bisect_right(self._page_top_offsets, viewport_bottom) - 1,
            first_visible,
        )
        return first_visible, last_visible

    def _page_vertical_bounds(
        self: _PageGeometryHost,
        page_index: int,
    ) -> tuple[int, int]:
        label_index = self._label_index_for_page(page_index)
        if label_index is None:
            return 0, 0

        return (
            self._page_top_offsets[label_index],
            self._page_bottom_offsets[label_index],
        )

    def _label_center(self: _PageGeometryHost, label_index: int) -> float:
        return (
            self._page_top_offsets[label_index]
            + self._page_bottom_offsets[label_index]
        ) / 2

    def _label_index_for_page(
        self: _PageGeometryHost,
        page_index: int | None,
    ) -> int | None:
        if page_index is None:
            return None

        try:
            return self._visible_page_indexes.index(page_index)
        except ValueError:
            return None

    def _geometry_cache_is_ready(self: _PageGeometryHost) -> bool:
        page_count = len(self._page_labels)
        return page_count > 0 and page_count == len(
            self._page_top_offsets,
        ) == len(self._page_bottom_offsets) == len(self._visible_page_indexes)
