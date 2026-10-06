"""Live ctrl+wheel zoom preview that defers rasterization until settled.

- Each wheel notch resizes the existing page labels and rescales the pixmaps
  already on screen, so a zoom gesture never tears down page widgets or waits
  on a render.
- A crisp re-render of the visible pages runs once the gesture goes idle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import QPointF, QSize, Qt, QTimer

from src.adapters.document.pymupdf.document import display_size_for_page_size
from src.gui.views.rendering.page_metrics import PAGE_CONTENT_CHROME

if TYPE_CHECKING:
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

    from src.domains.document.reader import PdfDocument
    from src.gui.models.window_state import RenderGenerations, SyncGuards
    from src.gui.views.rendering.page_surface import PageSurfaceLabel
    from src.gui.views.rendering.zoom.interaction import ZoomPageAnchor


#: Idle time after the last wheel notch before visible pages are re-rendered.
ZOOM_SETTLE_INTERVAL_MS = 120


@dataclass(slots=True)
class ZoomPreviewGesture:
    """Hold the page pixmaps and sizes reused across one zoom gesture.

    - `page_pixmaps` keeps the pixmaps as they were rasterized at the zoom the
      gesture started from, so every notch scales from the original rather
      than from the previous notch's already-scaled result.
    - `page_sizes` keeps unscaled page sizes so each notch can size labels
      exactly as a full rebuild would, without reloading pages.
    """

    page_pixmaps: dict[int, QPixmap] = field(default_factory=dict)
    page_sizes: dict[int, tuple[float, float]] = field(default_factory=dict)


class _ZoomPreviewHost(Protocol):
    """Describe the main-window API required by ZoomPreviewMixin."""

    _document: PdfDocument
    _document_container: QWidget
    _document_layout: QVBoxLayout
    _document_scroll_area: QScrollArea
    _generations: RenderGenerations
    _sync: SyncGuards
    _page_labels: list[QLabel]
    _visible_page_indexes: list[int]
    _rendered_page_indexes: set[int]
    _zoom_preview_gesture: ZoomPreviewGesture | None
    _zoom_settle_timer: QTimer

    def _cancel_pending_zoom_scroll_restore(self) -> None: ...
    def _label_index_for_page(
        self,
        page_index: int | None,
    ) -> int | None: ...
    def _page_anchor_for_zoom(
        self,
        *,
        content_x: float,
        content_y: float,
    ) -> ZoomPageAnchor | None: ...
    def _page_vertical_bounds(self, page_index: int) -> tuple[int, int]: ...
    def _rebuild_page_geometry_cache(self) -> None: ...
    def _refresh_visible_pages(self) -> None: ...
    def _render_device_pixel_ratio(self) -> float: ...
    def _reset_render_request_scope(self) -> None: ...
    def _sync_current_page_ui(self, *, scroll_to_page: bool) -> None: ...
    def _sync_page_selector(self) -> None: ...
    def _update_current_page_highlight(self) -> None: ...
    def _update_status_bar(self) -> None: ...
    def _visible_page_index(self) -> int | None: ...
    def _zoom_scroll_layout_ready(self) -> bool: ...
    def _apply_zoom_preview_anchor(
        self,
        *,
        page_anchor: ZoomPageAnchor | None,
        anchor_position: QPointF,
        fallback_targets: tuple[int, int],
    ) -> None: ...

    def _capture_zoom_preview_anchor(
        self,
        *,
        anchor_position: QPointF,
        zoom_ratio: float,
    ) -> tuple[ZoomPageAnchor | None, tuple[int, int]]: ...

    def _ensure_zoom_preview_gesture(
        self,
    ) -> ZoomPreviewGesture: ...

    def _resize_pages_for_zoom_preview(
        self,
        *,
        gesture: ZoomPreviewGesture,
        updated_zoom: float,
    ) -> None: ...

    def _set_zoom_preview_scroll(
        self,
        *,
        horizontal_target: int,
        vertical_target: int,
    ) -> None: ...

    def _sync_zoom_preview_page(self) -> None: ...


class ZoomPreviewMixin:
    """Scale the visible pages during a zoom gesture and render once idle."""

    if TYPE_CHECKING:
        # Declared so the type matches _ZoomPreviewHost rather than being
        # inferred as non-optional from the assignment below.
        _zoom_preview_gesture: ZoomPreviewGesture | None

    def _apply_zoom_preview(
        self: _ZoomPreviewHost,
        target_zoom: float,
        *,
        anchor_position: QPointF,
    ) -> None:
        """Zoom to `target_zoom` by rescaling the pages already on screen.

        - Keeps the document point under `anchor_position` in place.
        - Restarts the settle timer so the crisp re-render happens once the
          gesture stops.
        """
        if not self._document.has_document() or not self._page_labels:
            return

        previous_zoom = self._document.state.zoom
        self._document.state.set_zoom(target_zoom)
        updated_zoom = self._document.state.zoom
        if updated_zoom == previous_zoom:
            return

        # A restore queued by the discrete zoom path describes the layout from
        # before this preview, so letting it run would fight the anchor here.
        self._cancel_pending_zoom_scroll_restore()

        gesture = self._ensure_zoom_preview_gesture()
        page_anchor, fallback_targets = self._capture_zoom_preview_anchor(
            anchor_position=anchor_position,
            zoom_ratio=updated_zoom / previous_zoom,
        )
        self._resize_pages_for_zoom_preview(
            gesture=gesture,
            updated_zoom=updated_zoom,
        )
        self._apply_zoom_preview_anchor(
            page_anchor=page_anchor,
            anchor_position=anchor_position,
            fallback_targets=fallback_targets,
        )
        self._sync_zoom_preview_page()
        self._zoom_settle_timer.start()

    def _ensure_zoom_preview_gesture(
        self: _ZoomPreviewHost,
    ) -> ZoomPreviewGesture:
        """Return the active gesture, snapshotting page state on first use."""
        gesture = self._zoom_preview_gesture
        if gesture is not None:
            return gesture

        gesture = ZoomPreviewGesture()
        for label_index, page_index in enumerate(self._visible_page_indexes):
            gesture.page_sizes[page_index] = self._document.page_size_points(
                page_index,
            )
            if page_index not in self._rendered_page_indexes:
                continue

            page_pixmap = self._page_labels[label_index].pixmap()
            if not page_pixmap.isNull():
                gesture.page_pixmaps[page_index] = page_pixmap

        self._zoom_preview_gesture = gesture
        return gesture

    def _resize_pages_for_zoom_preview(
        self: _ZoomPreviewHost,
        *,
        gesture: ZoomPreviewGesture,
        updated_zoom: float,
    ) -> None:
        """Resize every page label and rescale the pixmaps it already shows."""
        device_pixel_ratio = self._render_device_pixel_ratio()
        for label_index, page_index in enumerate(self._visible_page_indexes):
            page_size = gesture.page_sizes.get(page_index)
            if page_size is None:
                continue

            page_width, page_height = display_size_for_page_size(
                page_size,
                zoom=updated_zoom,
            )
            page_label = self._page_labels[label_index]
            source_pixmap = gesture.page_pixmaps.get(page_index)
            if source_pixmap is not None:
                page_label.setPixmap(
                    _scaled_preview_pixmap(
                        source_pixmap,
                        page_width=page_width,
                        page_height=page_height,
                        device_pixel_ratio=device_pixel_ratio,
                    ),
                )
            page_label.setFixedSize(
                page_width + PAGE_CONTENT_CHROME,
                page_height + PAGE_CONTENT_CHROME,
            )
            page_surface: PageSurfaceLabel = page_label  # type: ignore[assignment]
            page_surface.set_page_zoom(zoom=updated_zoom)

        self._document_layout.activate()
        self._document_container.adjustSize()
        self._rebuild_page_geometry_cache()

    def _capture_zoom_preview_anchor(
        self: _ZoomPreviewHost,
        *,
        anchor_position: QPointF,
        zoom_ratio: float,
    ) -> tuple[ZoomPageAnchor | None, tuple[int, int]]:
        """Record the document point under the cursor before pages resize.

        Returns:
            The page-relative anchor when the cursor sits on a page, paired
            with the scroll targets to use when it does not.

        """
        horizontal_bar = self._document_scroll_area.horizontalScrollBar()
        vertical_bar = self._document_scroll_area.verticalScrollBar()
        content_x = horizontal_bar.value() + anchor_position.x()
        content_y = vertical_bar.value() + anchor_position.y()
        fallback_targets = (
            int((content_x * zoom_ratio) - anchor_position.x()),
            int((content_y * zoom_ratio) - anchor_position.y()),
        )
        page_anchor = self._page_anchor_for_zoom(
            content_x=content_x,
            content_y=content_y,
        )
        return page_anchor, fallback_targets

    def _apply_zoom_preview_anchor(
        self: _ZoomPreviewHost,
        *,
        page_anchor: ZoomPageAnchor | None,
        anchor_position: QPointF,
        fallback_targets: tuple[int, int],
    ) -> None:
        """Scroll so the captured anchor sits back under the cursor.

        - Page labels were resized in place, so the layout is already current
          and the targets can be applied without waiting for a render.
        - The scroll area can still report a stale range on the same pass, so
          the targets are reapplied once more when that happens.
        """
        horizontal_target, vertical_target = fallback_targets
        label_index = self._label_index_for_page(
            page_anchor.page_index if page_anchor is not None else None,
        )
        if page_anchor is not None and label_index is not None:
            page_label = self._page_labels[label_index]
            page_top, _ = self._page_vertical_bounds(page_anchor.page_index)
            inset = PAGE_CONTENT_CHROME / 2
            content_width = max(page_label.width() - PAGE_CONTENT_CHROME, 1)
            content_height = max(page_label.height() - PAGE_CONTENT_CHROME, 1)
            horizontal_target = int(
                page_label.x()
                + inset
                + (page_anchor.horizontal_ratio * content_width)
                - anchor_position.x(),
            )
            vertical_target = int(
                page_top
                + inset
                + (page_anchor.vertical_ratio * content_height)
                - anchor_position.y(),
            )

        self._set_zoom_preview_scroll(
            horizontal_target=horizontal_target,
            vertical_target=vertical_target,
        )
        if self._zoom_scroll_layout_ready():
            return

        QTimer.singleShot(
            0,
            lambda: self._set_zoom_preview_scroll(
                horizontal_target=horizontal_target,
                vertical_target=vertical_target,
            ),
        )

    def _set_zoom_preview_scroll(
        self: _ZoomPreviewHost,
        *,
        horizontal_target: int,
        vertical_target: int,
    ) -> None:
        """Clamp and apply scroll targets without triggering a page refresh."""
        if not self._document.has_document():
            return

        horizontal_bar = self._document_scroll_area.horizontalScrollBar()
        vertical_bar = self._document_scroll_area.verticalScrollBar()
        self._sync.scroll_position = True
        horizontal_bar.setValue(
            min(max(horizontal_target, 0), horizontal_bar.maximum()),
        )
        vertical_bar.setValue(
            min(max(vertical_target, 0), vertical_bar.maximum()),
        )
        self._sync.scroll_position = False

    def _sync_zoom_preview_page(self: _ZoomPreviewHost) -> None:
        """Track the anchored page in the page number, highlight, and status.

        - The full page sync also refreshes thumbnails, bookmarks, and the
          text panel, which is far too much work to repeat per wheel notch,
          so a gesture only updates what reports the page and zoom.
        """
        visible_page_index = self._visible_page_index()
        if visible_page_index is not None:
            self._document.go_to_page(visible_page_index, record_history=False)

        self._update_current_page_highlight()
        self._sync_page_selector()
        self._update_status_bar()

    def _settle_zoom_preview(self: _ZoomPreviewHost) -> None:
        """Re-render the visible pages once the zoom gesture goes idle."""
        self._zoom_settle_timer.stop()
        if self._zoom_preview_gesture is None:
            return

        self._zoom_preview_gesture = None
        if not self._document.has_document() or not self._page_labels:
            return

        # Scaled previews stay on screen while the crisp pixmaps render, so
        # the pages never fall back to placeholder text after a gesture.
        self._generations.render += 1
        self._reset_render_request_scope()
        self._rendered_page_indexes.clear()
        self._refresh_visible_pages()

        visible_page_index = self._visible_page_index()
        if visible_page_index is not None:
            self._document.go_to_page(visible_page_index, record_history=False)
        self._sync_current_page_ui(scroll_to_page=False)

    def _cancel_zoom_preview(self: _ZoomPreviewHost) -> None:
        """Drop gesture state so a rebuild is not undone by a stale preview."""
        self._zoom_settle_timer.stop()
        self._zoom_preview_gesture = None


def _scaled_preview_pixmap(
    source_pixmap: QPixmap,
    *,
    page_width: int,
    page_height: int,
    device_pixel_ratio: float,
) -> QPixmap:
    """Return `source_pixmap` stretched to the page's new on-screen size."""
    scaled_pixmap = source_pixmap.scaled(
        QSize(
            max(round(page_width * device_pixel_ratio), 1),
            max(round(page_height * device_pixel_ratio), 1),
        ),
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )
    scaled_pixmap.setDevicePixelRatio(device_pixel_ratio)
    return scaled_pixmap
