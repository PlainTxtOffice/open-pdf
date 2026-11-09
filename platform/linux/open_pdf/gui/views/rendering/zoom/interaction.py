"""Zoom interaction and scroll-restoration presentation behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import QPointF, QTimer

from open_pdf.gui.views.rendering.page_metrics import PAGE_CONTENT_CHROME

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout

    from open_pdf.application.document.session import PdfDocument
    from open_pdf.gui.models.window_state import RenderGenerations, SyncGuards


_CTRL_WHEEL_ZOOM_FACTOR = 1.1
_CTRL_WHEEL_DELTA_STEP = 120
#: Trackpads report smooth pixel scrolling instead of notches; this many
#: pixels of vertical travel counts as one notch worth of zoom.
_CTRL_WHEEL_PIXEL_STEP = 50


@dataclass(slots=True)
class ZoomPageAnchor:
    """Describe the page-relative point that should stay under the mouse."""

    page_index: int
    horizontal_ratio: float
    vertical_ratio: float


@dataclass(slots=True)
class ZoomScrollRestore:
    """Store the scroll position to restore after a zoom rerender."""

    restore_page_index: int
    anchor_position: QPointF
    horizontal_target_value: int
    vertical_target_value: int
    page_anchor: ZoomPageAnchor | None = None
    render_generation: int = 0
    layout_retries_remaining: int = 5


class _ZoomInteractionHost(Protocol):
    """Describe the main-window API required by ZoomInteractionMixin."""

    _document: PdfDocument
    _document_layout: QVBoxLayout
    _document_scroll_area: QScrollArea
    _generations: RenderGenerations
    _sync: SyncGuards
    _pending_zoom_scroll_restore: ZoomScrollRestore | None
    _page_labels: list[QLabel]
    _visible_page_indexes: list[int]
    _page_bottom_offsets: list[int]

    def _cancel_zoom_preview(self) -> None: ...
    def _refresh_document_view(self, *, scroll_to_page: bool) -> None: ...
    def _label_index_for_page(
        self,
        page_index: int | None,
    ) -> int | None: ...
    def _page_vertical_bounds(self, page_index: int) -> tuple[int, int]: ...
    def _refresh_visible_pages(self) -> None: ...
    def _visible_page_index(self) -> int | None: ...
    def _sync_current_page_ui(self, *, scroll_to_page: bool) -> None: ...
    def _apply_zoom(
        self,
        target_zoom: float,
        *,
        anchor_position: QPointF | None = None,
    ) -> None: ...

    def _calculate_fit_zoom(
        self,
        *,
        fit_height: bool,
    ) -> float | None: ...

    def _capture_zoom_scroll_restore(
        self,
        *,
        anchor_position: QPointF | None,
        previous_zoom: float,
        updated_zoom: float,
    ) -> ZoomScrollRestore: ...

    def _carry_forward_zoom_scroll_restore(
        self,
        *,
        pending: ZoomScrollRestore,
        anchor: QPointF,
    ) -> ZoomScrollRestore: ...

    def _change_zoom(
        self,
        *,
        zoom_in: bool,
        anchor_position: QPointF | None = None,
    ) -> None: ...

    def _handle_zoom_change(
        self,
        *,
        previous_zoom: float,
        updated_zoom: float,
        anchor_position: QPointF | None,
    ) -> None: ...

    def _page_anchor_for_zoom(
        self,
        *,
        content_x: float,
        content_y: float,
    ) -> ZoomPageAnchor | None: ...

    def _page_anchor_ratio_for_zoom(
        self,
        *,
        current_page_index: int,
        content_y: float,
    ) -> float | None: ...

    def _page_index_for_vertical_position(
        self,
        *,
        content_y: float,
    ) -> int | None: ...

    def _restore_page_index_for_zoom(
        self,
        *,
        content_y: float,
        page_anchor: ZoomPageAnchor | None,
    ) -> int: ...

    def _restore_zoom_scroll_position(
        self,
        *,
        scroll_restore: ZoomScrollRestore,
    ) -> None: ...

    def _zoom_restore_target_values(
        self,
        scroll_restore: ZoomScrollRestore,
    ) -> tuple[int, int]: ...

    def _zoom_scroll_layout_ready(self) -> bool: ...

    def _zoom_vertical_target_value(
        self,
        *,
        anchor: QPointF,
        content_y: float,
        zoom_ratio: float,
        current_page_index: int,
        page_anchor_ratio: float | None,
    ) -> int: ...


class ZoomInteractionMixin:
    """Coordinate zoom commands and preserve the visible document anchor."""

    if TYPE_CHECKING:
        # Declared so the type matches _ZoomInteractionHost rather than
        # being inferred as None from the assignments below.
        _pending_zoom_scroll_restore: ZoomScrollRestore | None

    def _cancel_pending_zoom_scroll_restore(self: _ZoomInteractionHost) -> None:
        """Drop a queued restore that describes a superseded page layout."""
        self._pending_zoom_scroll_restore = None

    def _zoom_in(self: _ZoomInteractionHost) -> None:
        self._change_zoom(zoom_in=True)

    def _zoom_out(self: _ZoomInteractionHost) -> None:
        self._change_zoom(zoom_in=False)

    def _zoom_to_actual_size(self: _ZoomInteractionHost) -> None:
        self._apply_zoom(1.0)

    def _zoom_fit_width(self: _ZoomInteractionHost) -> None:
        target_zoom = self._calculate_fit_zoom(fit_height=False)
        if target_zoom is not None:
            self._apply_zoom(target_zoom)

    def _zoom_fit_page(self: _ZoomInteractionHost) -> None:
        target_zoom = self._calculate_fit_zoom(fit_height=True)
        if target_zoom is not None:
            self._apply_zoom(target_zoom)

    def _apply_zoom(
        self: _ZoomInteractionHost,
        target_zoom: float,
        *,
        anchor_position: QPointF | None = None,
    ) -> None:
        if not self._document.has_document():
            return

        previous_zoom = self._document.state.zoom
        self._document.state.set_zoom(target_zoom)
        self._handle_zoom_change(
            previous_zoom=previous_zoom,
            updated_zoom=self._document.state.zoom,
            anchor_position=anchor_position,
        )

    def _handle_zoom_change(
        self: _ZoomInteractionHost,
        *,
        previous_zoom: float,
        updated_zoom: float,
        anchor_position: QPointF | None,
    ) -> None:
        # A discrete zoom rebuilds the page labels a preview gesture was
        # rescaling, so any settle pending for that gesture is now stale.
        self._cancel_zoom_preview()
        if updated_zoom == previous_zoom:
            return

        if anchor_position is None:
            self._refresh_document_view(scroll_to_page=True)
            return

        scroll_restore = self._capture_zoom_scroll_restore(
            anchor_position=anchor_position,
            previous_zoom=previous_zoom,
            updated_zoom=updated_zoom,
        )

        self._refresh_document_view(scroll_to_page=False)

        scroll_restore.render_generation = self._generations.render
        self._pending_zoom_scroll_restore = scroll_restore
        QTimer.singleShot(
            0,
            lambda: self._restore_zoom_scroll_position(
                scroll_restore=scroll_restore,
            ),
        )

    def _ctrl_wheel_zoom_target(
        self: _ZoomInteractionHost,
        *,
        angle_delta_y: int,
        pixel_delta_y: int = 0,
    ) -> float | None:
        """Return the zoom one ctrl+wheel event asks for, or None for no-ops.

        - Prefers `pixel_delta_y`, which trackpads report as smooth travel,
          so pinch and two-finger zoom scale continuously instead of jumping
          a full notch at a time.
        """
        if not self._document.has_document():
            return None

        if pixel_delta_y != 0:
            zoom_steps = pixel_delta_y / _CTRL_WHEEL_PIXEL_STEP
        elif angle_delta_y != 0:
            zoom_steps = angle_delta_y / _CTRL_WHEEL_DELTA_STEP
        else:
            return None

        return self._document.state.zoom * (_CTRL_WHEEL_ZOOM_FACTOR**zoom_steps)

    def _calculate_fit_zoom(
        self: _ZoomInteractionHost,
        *,
        fit_height: bool,
    ) -> float | None:
        if not self._document.has_document():
            return None

        page = self._document.current_page()
        page_width = max(float(page.rect.width), 1.0)
        page_height = max(float(page.rect.height), 1.0)

        margins = self._document_layout.contentsMargins()
        horizontal_margin = margins.left() + margins.right()
        vertical_margin = margins.top() + margins.bottom()
        label_chrome = PAGE_CONTENT_CHROME

        viewport = self._document_scroll_area.viewport()
        available_width = viewport.width() - horizontal_margin - label_chrome
        if available_width <= 0:
            return None

        width_zoom = available_width / page_width
        if not fit_height:
            return width_zoom

        available_height = viewport.height() - vertical_margin - label_chrome
        if available_height <= 0:
            return None

        height_zoom = available_height / page_height
        return min(width_zoom, height_zoom)

    def _change_zoom(
        self: _ZoomInteractionHost,
        *,
        zoom_in: bool,
        anchor_position: QPointF | None = None,
    ) -> None:
        if not self._document.has_document():
            return

        previous_zoom = self._document.state.zoom
        if zoom_in:
            self._document.zoom_in()
        else:
            self._document.zoom_out()

        if anchor_position is None:
            viewport = self._document_scroll_area.viewport()
            anchor_position = QPointF(
                viewport.width() / 2,
                viewport.height() / 2,
            )

        self._handle_zoom_change(
            previous_zoom=previous_zoom,
            updated_zoom=self._document.state.zoom,
            anchor_position=anchor_position,
        )

    def _capture_zoom_scroll_restore(
        self: _ZoomInteractionHost,
        *,
        anchor_position: QPointF | None,
        previous_zoom: float,
        updated_zoom: float,
    ) -> ZoomScrollRestore:
        viewport = self._document_scroll_area.viewport()
        anchor = anchor_position or QPointF(
            viewport.width() / 2,
            viewport.height() / 2,
        )
        pending = self._pending_zoom_scroll_restore
        if (
            pending is not None
            and pending.render_generation == self._generations.render
        ):
            return self._carry_forward_zoom_scroll_restore(
                pending=pending,
                anchor=anchor,
            )

        horizontal_bar = self._document_scroll_area.horizontalScrollBar()
        vertical_bar = self._document_scroll_area.verticalScrollBar()
        content_x = horizontal_bar.value() + anchor.x()
        content_y = vertical_bar.value() + anchor.y()
        page_anchor = self._page_anchor_for_zoom(
            content_x=content_x,
            content_y=content_y,
        )
        zoom_ratio = updated_zoom / previous_zoom
        restore_page_index = self._restore_page_index_for_zoom(
            content_y=content_y,
            page_anchor=page_anchor,
        )
        page_anchor_ratio = self._page_anchor_ratio_for_zoom(
            current_page_index=restore_page_index,
            content_y=content_y,
        )
        horizontal_target_value = int((content_x * zoom_ratio) - anchor.x())
        vertical_target_value = self._zoom_vertical_target_value(
            anchor=anchor,
            content_y=content_y,
            zoom_ratio=zoom_ratio,
            current_page_index=restore_page_index,
            page_anchor_ratio=page_anchor_ratio,
        )
        return ZoomScrollRestore(
            restore_page_index=restore_page_index,
            anchor_position=anchor,
            horizontal_target_value=horizontal_target_value,
            vertical_target_value=vertical_target_value,
            page_anchor=page_anchor,
        )

    def _carry_forward_zoom_scroll_restore(
        self: _ZoomInteractionHost,
        *,
        pending: ZoomScrollRestore,
        anchor: QPointF,
    ) -> ZoomScrollRestore:
        """Reuse a still-pending restore's anchor for the next zoom step.

        - Until the pending restore runs, the scroll bars and page label
          positions do not reflect the rebuilt layout, so reading them would
          anchor the capture near the top of the document.
        - The pending page anchor stores page-relative ratios, which stay
          valid across zoom levels, so it can carry over unchanged.
        """
        vertical_target_value = pending.vertical_target_value
        page_anchor = pending.page_anchor
        if (
            page_anchor is not None
            and self._label_index_for_page(page_anchor.page_index) is not None
        ):
            page_top, page_bottom = self._page_vertical_bounds(
                page_anchor.page_index,
            )
            inset = PAGE_CONTENT_CHROME / 2
            content_height = max(
                page_bottom - page_top - PAGE_CONTENT_CHROME,
                1,
            )
            vertical_target_value = int(
                page_top
                + inset
                + (page_anchor.vertical_ratio * content_height)
                - anchor.y(),
            )

        return ZoomScrollRestore(
            restore_page_index=pending.restore_page_index,
            anchor_position=anchor,
            horizontal_target_value=pending.horizontal_target_value,
            vertical_target_value=vertical_target_value,
            page_anchor=page_anchor,
        )

    def _zoom_restore_target_values(
        self: _ZoomInteractionHost,
        scroll_restore: ZoomScrollRestore,
    ) -> tuple[int, int]:
        """Resolve a zoom restore's scroll targets against current geometry.

        - Prefers re-deriving the targets from the anchored page label so the
          point under the mouse stays put after page labels are rebuilt.
        """
        horizontal_target_value = scroll_restore.horizontal_target_value
        vertical_target_value = scroll_restore.vertical_target_value
        page_anchor = scroll_restore.page_anchor
        page_anchor_label_index = self._label_index_for_page(
            page_anchor.page_index if page_anchor is not None else None,
        )
        if page_anchor is not None and page_anchor_label_index is not None:
            page_label = self._page_labels[page_anchor_label_index]
            inset = PAGE_CONTENT_CHROME / 2
            content_width = max(page_label.width() - PAGE_CONTENT_CHROME, 1)
            content_height = max(page_label.height() - PAGE_CONTENT_CHROME, 1)
            anchored_content_x = (
                page_label.x()
                + inset
                + (page_anchor.horizontal_ratio * content_width)
            )
            anchored_content_y = (
                page_label.y()
                + inset
                + (page_anchor.vertical_ratio * content_height)
            )
            horizontal_target_value = int(
                anchored_content_x - scroll_restore.anchor_position.x(),
            )
            vertical_target_value = int(
                anchored_content_y - scroll_restore.anchor_position.y(),
            )

        return horizontal_target_value, vertical_target_value

    def _restore_page_index_for_zoom(
        self: _ZoomInteractionHost,
        *,
        content_y: float,
        page_anchor: ZoomPageAnchor | None,
    ) -> int:
        if page_anchor is not None:
            return page_anchor.page_index

        page_index = self._page_index_for_vertical_position(
            content_y=content_y,
        )
        if page_index is not None:
            return page_index

        return self._document.state.current_page_index

    def _page_index_for_vertical_position(
        self: _ZoomInteractionHost,
        *,
        content_y: float,
    ) -> int | None:
        closest_page_index: int | None = None
        closest_distance: float | None = None

        for page_index in self._visible_page_indexes:
            page_top, page_bottom = self._page_vertical_bounds(page_index)
            if page_top <= content_y <= page_bottom:
                return page_index

            distance = min(
                abs(content_y - page_top),
                abs(content_y - page_bottom),
            )
            if closest_distance is None or distance < closest_distance:
                closest_distance = distance
                closest_page_index = page_index

        return closest_page_index

    def _page_anchor_for_zoom(
        self: _ZoomInteractionHost,
        *,
        content_x: float,
        content_y: float,
    ) -> ZoomPageAnchor | None:
        for label_index, page_label in enumerate(self._page_labels):
            page_index = self._visible_page_indexes[label_index]
            page_left = float(page_label.x())
            page_top = float(page_label.y())
            page_right = page_left + page_label.width()
            page_bottom = page_top + page_label.height()
            if not (
                page_left <= content_x <= page_right
                and page_top <= content_y <= page_bottom
            ):
                continue

            inset = PAGE_CONTENT_CHROME / 2
            content_width = max(page_label.width() - PAGE_CONTENT_CHROME, 1)
            content_height = max(page_label.height() - PAGE_CONTENT_CHROME, 1)
            content_offset_x = min(
                max(content_x - page_left - inset, 0.0),
                content_width,
            )
            content_offset_y = min(
                max(content_y - page_top - inset, 0.0),
                content_height,
            )
            return ZoomPageAnchor(
                page_index=page_index,
                horizontal_ratio=content_offset_x / content_width,
                vertical_ratio=content_offset_y / content_height,
            )

        return None

    def _page_anchor_ratio_for_zoom(
        self: _ZoomInteractionHost,
        *,
        current_page_index: int,
        content_y: float,
    ) -> float | None:
        if self._label_index_for_page(current_page_index) is None:
            return None

        page_top, page_bottom = self._page_vertical_bounds(
            current_page_index,
        )
        page_height = max(page_bottom - page_top, 1)
        clamped_anchor_y = min(max(content_y, page_top), page_bottom)
        return (clamped_anchor_y - page_top) / page_height

    def _zoom_vertical_target_value(
        self: _ZoomInteractionHost,
        *,
        anchor: QPointF,
        content_y: float,
        zoom_ratio: float,
        current_page_index: int,
        page_anchor_ratio: float | None,
    ) -> int:
        vertical_target_value = int((content_y * zoom_ratio) - anchor.y())
        if (
            page_anchor_ratio is None
            or self._label_index_for_page(current_page_index) is None
        ):
            return vertical_target_value

        page_top, page_bottom = self._page_vertical_bounds(
            current_page_index,
        )
        page_height = max(page_bottom - page_top, 1)
        return int((page_top + (page_anchor_ratio * page_height)) - anchor.y())

    def _zoom_scroll_layout_ready(self: _ZoomInteractionHost) -> bool:
        """Report whether the scroll range matches the rebuilt page layout.

        - After page labels are rebuilt for a zoom change, the scroll area
          only picks up the new content extent on a later layout pass; until
          then its scroll range still describes the old layout.
        """
        if not self._page_bottom_offsets:
            return True

        vertical_bar = self._document_scroll_area.verticalScrollBar()
        viewport_height = self._document_scroll_area.viewport().height()
        expected_content_height = (
            self._page_bottom_offsets[-1]
            + self._document_layout.contentsMargins().bottom()
        )
        return (
            vertical_bar.maximum() + viewport_height >= expected_content_height
        )

    def _restore_zoom_scroll_position(
        self: _ZoomInteractionHost,
        *,
        scroll_restore: ZoomScrollRestore,
    ) -> None:
        if (
            not self._document.has_document()
            or scroll_restore.render_generation != self._generations.render
        ):
            if self._pending_zoom_scroll_restore is scroll_restore:
                self._pending_zoom_scroll_restore = None
            return

        if (
            not self._zoom_scroll_layout_ready()
            and scroll_restore.layout_retries_remaining > 0
        ):
            # The rebuilt page layout has not been applied to the scroll
            # area yet; restoring now would clamp the scroll bars to a
            # stale range. Try again on the next event-loop pass.
            scroll_restore.layout_retries_remaining -= 1
            QTimer.singleShot(
                0,
                lambda: self._restore_zoom_scroll_position(
                    scroll_restore=scroll_restore,
                ),
            )
            return

        if self._pending_zoom_scroll_restore is scroll_restore:
            self._pending_zoom_scroll_restore = None

        horizontal_bar = self._document_scroll_area.horizontalScrollBar()
        vertical_bar = self._document_scroll_area.verticalScrollBar()
        horizontal_target_value, vertical_target_value = (
            self._zoom_restore_target_values(scroll_restore)
        )

        self._sync.scroll_position = True
        horizontal_bar.setValue(
            min(max(horizontal_target_value, 0), horizontal_bar.maximum()),
        )
        vertical_bar.setValue(
            min(max(vertical_target_value, 0), vertical_bar.maximum()),
        )
        self._sync.scroll_position = False

        self._refresh_visible_pages()
        visible_page_index = self._visible_page_index()
        if visible_page_index is None:
            visible_page_index = scroll_restore.restore_page_index

        self._document.go_to_page(visible_page_index, record_history=False)
        self._sync_current_page_ui(scroll_to_page=False)
