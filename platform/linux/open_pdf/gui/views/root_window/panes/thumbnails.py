"""Thumbnail navigation behavior for the PySide6 PDF window."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QListWidgetItem, QMenu, QMessageBox, QStyle

from open_pdf.adapters.document.errors import PDF_IO_ERRORS
from open_pdf.adapters.document.pymupdf.qt import pixmap_from_pymupdf
from open_pdf.gui.views.rendering.thumbnail_rendering import ThumbnailRenderTask

if TYPE_CHECKING:
    from pathlib import Path

    from PySide6.QtCore import QThreadPool, QTimer
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QListWidget

    from open_pdf.application.document.session import PdfDocument
    from open_pdf.gui.models.window_state import RenderGenerations, SyncGuards

logger = logging.getLogger(__name__)

# Single source of truth for thumbnail sizing: the base on-screen icon box.
# The cell, pane width, and render resolution are all derived from it so
# the navigation pane cannot reserve space the thumbnails never use. When
# the pane is dragged wider, the icon box scales up from this base while
# keeping its aspect ratio. Cell padding comes from style metrics.
_THUMBNAIL_ICON_SIZE = QSize(140, 180)
# Render at 2x the icon box so thumbnails stay crisp on HiDPI displays.
_THUMBNAIL_RENDER_SCALE = 2


class _ThumbnailNavigationHost(Protocol):
    """Describe the main-window API required by ThumbnailNavigationMixin."""

    _sync: SyncGuards
    _generations: RenderGenerations
    _document: PdfDocument
    _thumbnail_list: QListWidget
    _thumbnail_rendered_pages: set[int]
    _thumbnail_pending_pages: set[int]
    _thumbnail_rerender_timer: QTimer
    _thread_pool: QThreadPool

    def _clear_search_results(self) -> None: ...
    def _populate_bookmarks(self) -> None: ...
    def _refresh_document_view(self, *, scroll_to_page: bool) -> None: ...
    def _show_error(self, message: str) -> None: ...
    def _sync_current_page_ui(self, *, scroll_to_page: bool) -> None: ...
    def _rotate_current_page(self) -> None: ...
    def _delete_thumbnail_page(
        self,
        page_index: int,
    ) -> None: ...

    def _handle_thumbnail_render_failed(
        self,
        generation: int,
        page_index: int,
        _error_message: str,
    ) -> None: ...

    def _handle_thumbnail_rendered(
        self,
        generation: int,
        page_index: int,
        image: QImage,
    ) -> None: ...

    def _populate_thumbnails(self) -> None: ...

    def _queue_thumbnail_render(
        self,
        page_index: int,
        *,
        source_path: Path,
    ) -> None: ...

    def _refresh_visible_thumbnails(self) -> None: ...

    def _render_dirty_thumbnail(
        self,
        page_index: int,
    ) -> None: ...

    def _rotate_thumbnail_page(
        self,
        page_index: int,
    ) -> None: ...

    def _thumbnail_cell_padding(self) -> QSize: ...

    def _thumbnail_item_size(self) -> QSize: ...

    @staticmethod
    def _thumbnail_item_text(_page_index: int) -> str: ...

    def _thumbnail_page_aspect(self) -> float: ...

    def _thumbnail_render_max_dimension(self) -> int: ...

    def _update_thumbnail_grid_size(self) -> None: ...

    def _visible_thumbnail_range(
        self,
    ) -> tuple[int, int] | None: ...


class ThumbnailNavigationMixin:
    """Populate and react to the thumbnail navigation pane."""

    def _handle_thumbnail_selected(
        self: _ThumbnailNavigationHost,
        page_index: int,
    ) -> None:
        if self._sync.thumbnail_list or page_index < 0:
            return

        if not self._document.has_document():
            return

        self._document.go_to_page(page_index)
        self._sync_current_page_ui(scroll_to_page=True)

    def _show_thumbnail_context_menu(
        self: _ThumbnailNavigationHost,
        position: QPoint,
    ) -> None:
        if not self._document.has_document():
            return

        item = self._thumbnail_list.itemAt(position)
        if item is None:
            return

        page_index = self._thumbnail_list.row(item)
        if page_index < 0:
            return

        menu = QMenu(self._thumbnail_list)
        rotate_action = menu.addAction("Rotate Right")
        delete_action = menu.addAction("Delete Page")
        selected_action = menu.exec(
            self._thumbnail_list.viewport().mapToGlobal(position),
        )
        if selected_action is rotate_action:
            self._rotate_thumbnail_page(page_index)
        elif selected_action is delete_action:
            self._delete_thumbnail_page(page_index)

    def _rotate_thumbnail_page(
        self: _ThumbnailNavigationHost,
        page_index: int,
    ) -> None:
        """Rotate the page represented by one thumbnail."""
        if not 0 <= page_index < self._document.state.page_count:
            return

        self._document.go_to_page(page_index)
        self._rotate_current_page()

    def _delete_thumbnail_page(
        self: _ThumbnailNavigationHost,
        page_index: int,
    ) -> None:
        if not self._document.has_document():
            return

        if not 0 <= page_index < self._document.state.page_count:
            return

        confirmation = QMessageBox.question(
            self._thumbnail_list,
            "Delete Page",
            f"Delete page {page_index + 1}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        try:
            self._document.delete_page(page_index)
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to delete page:\n{error}")
            return

        self._clear_search_results()
        self._populate_bookmarks()
        self._populate_thumbnails()
        self._refresh_document_view(scroll_to_page=True)

    def _populate_thumbnails(self: _ThumbnailNavigationHost) -> None:
        self._generations.thumbnail += 1
        self._thumbnail_list.clear()
        self._thumbnail_rendered_pages.clear()
        self._thumbnail_pending_pages.clear()
        if not self._document.has_document():
            return

        if self._document.source_path is None:
            return

        size_hint = self._thumbnail_list.gridSize()
        if not size_hint.isValid():
            size_hint = self._thumbnail_item_size()
        for page_index in range(self._document.state.page_count):
            item = QListWidgetItem(
                QIcon(),
                self._thumbnail_item_text(page_index),
            )
            item.setSizeHint(size_hint)
            self._thumbnail_list.addItem(item)

        self._update_thumbnail_grid_size()
        self._refresh_visible_thumbnails()

    def _handle_thumbnail_list_scrolled(
        self: _ThumbnailNavigationHost,
        _value: int,
    ) -> None:
        self._refresh_visible_thumbnails()

    def _refresh_visible_thumbnails(self: _ThumbnailNavigationHost) -> None:
        if not self._document.has_document():
            return

        source_path = self._document.source_path
        if source_path is None:
            return

        visible_range = self._visible_thumbnail_range()
        if visible_range is None:
            return

        first_row, last_row = visible_range
        for page_index in range(first_row, last_row + 1):
            self._queue_thumbnail_render(page_index, source_path=source_path)

    def _visible_thumbnail_range(
        self: _ThumbnailNavigationHost,
    ) -> tuple[int, int] | None:
        count = self._thumbnail_list.count()
        if count == 0:
            return None

        viewport = self._thumbnail_list.viewport()
        probe_x = viewport.width() // 2
        top_index = self._thumbnail_list.indexAt(QPoint(probe_x, 0))
        bottom_index = self._thumbnail_list.indexAt(
            QPoint(probe_x, max(viewport.height() - 1, 0)),
        )
        first_row = top_index.row() if top_index.isValid() else 0
        last_row = bottom_index.row() if bottom_index.isValid() else count - 1

        preload_margin = 3
        first_row = max(first_row - preload_margin, 0)
        last_row = min(last_row + preload_margin, count - 1)
        return first_row, last_row

    def _queue_thumbnail_render(
        self: _ThumbnailNavigationHost,
        page_index: int,
        *,
        source_path: Path,
    ) -> None:
        if page_index in self._thumbnail_rendered_pages:
            return
        if page_index in self._thumbnail_pending_pages:
            return

        if self._document.is_dirty():
            self._render_dirty_thumbnail(page_index)
            return

        self._thumbnail_pending_pages.add(page_index)
        task = ThumbnailRenderTask(
            source_path=source_path,
            render_revision=self._document.render_revision,
            page_index=page_index,
            max_dimension=self._thumbnail_render_max_dimension(),
            generation=self._generations.thumbnail,
        )
        task.signals.rendered.connect(self._handle_thumbnail_rendered)
        task.signals.failed.connect(self._handle_thumbnail_render_failed)
        self._thread_pool.start(task)

    def _handle_thumbnail_rendered(
        self: _ThumbnailNavigationHost,
        generation: int,
        page_index: int,
        image: QImage,
    ) -> None:
        self._thumbnail_pending_pages.discard(page_index)
        if generation != self._generations.thumbnail:
            return

        item = self._thumbnail_list.item(page_index)
        if item is None:
            return

        item.setIcon(QIcon(QPixmap.fromImage(image)))
        self._thumbnail_rendered_pages.add(page_index)

    def _handle_thumbnail_render_failed(
        self: _ThumbnailNavigationHost,
        generation: int,
        page_index: int,
        _error_message: str,
    ) -> None:
        self._thumbnail_pending_pages.discard(page_index)
        if generation != self._generations.thumbnail:
            return

        item = self._thumbnail_list.item(page_index)
        if item is None:
            return

        item.setText(f"Page {page_index + 1}")
        self._thumbnail_rendered_pages.add(page_index)

    def _render_dirty_thumbnail(
        self: _ThumbnailNavigationHost,
        page_index: int,
    ) -> None:
        item = self._thumbnail_list.item(page_index)
        if item is None:
            return

        try:
            thumbnail = pixmap_from_pymupdf(
                self._document.render_thumbnail(
                    page_index,
                    max_dimension=self._thumbnail_render_max_dimension(),
                ),
            )
        except PDF_IO_ERRORS:
            logger.exception(
                "Failed to render dirty thumbnail for page %d",
                page_index + 1,
            )
            item.setText(f"Page {page_index + 1}")
            self._thumbnail_rendered_pages.add(page_index)
            return

        item.setIcon(QIcon(thumbnail))
        self._thumbnail_rendered_pages.add(page_index)

    @staticmethod
    def _thumbnail_item_text(_page_index: int) -> str:
        return ""

    @staticmethod
    def _thumbnail_icon_size() -> QSize:
        return QSize(_THUMBNAIL_ICON_SIZE)

    def _thumbnail_cell_padding(self: _ThumbnailNavigationHost) -> QSize:
        """Return style-derived padding reserved around the icon box.

        Follows PDF4QT's approach: focus-frame margins horizontally, plus
        the style's layout spacing vertically to keep rows separated.
        """
        style = self._thumbnail_list.style()
        focus_margin = style.pixelMetric(
            QStyle.PixelMetric.PM_FocusFrameHMargin,
            None,
            self._thumbnail_list,
        )
        spacing = max(
            style.pixelMetric(
                QStyle.PixelMetric.PM_LayoutVerticalSpacing,
                None,
                self._thumbnail_list,
            ),
            0,
        )
        horizontal = 2 * (focus_margin + 1)
        return QSize(horizontal, horizontal + spacing)

    def _thumbnail_item_size(self: _ThumbnailNavigationHost) -> QSize:
        """Reserve stable space before asynchronous thumbnail rendering."""
        padding = self._thumbnail_cell_padding()
        return QSize(
            _THUMBNAIL_ICON_SIZE.width() + padding.width(),
            _THUMBNAIL_ICON_SIZE.height() + padding.height(),
        )

    def _thumbnail_render_max_dimension(self: _ThumbnailNavigationHost) -> int:
        icon_size = self._thumbnail_list.iconSize()
        if icon_size.isEmpty():
            icon_size = _THUMBNAIL_ICON_SIZE
        return _THUMBNAIL_RENDER_SCALE * max(
            icon_size.width(),
            icon_size.height(),
        )

    def _thumbnail_page_aspect(self: _ThumbnailNavigationHost) -> float:
        """Return the first page's height-to-width ratio.

        - clamped to sane bounds
        - so unusual page shapes cannot produce extreme cells.
        """
        base_aspect = (
            _THUMBNAIL_ICON_SIZE.height() / _THUMBNAIL_ICON_SIZE.width()
        )
        if (
            not self._document.has_document()
            or self._document.state.page_count == 0
        ):
            return base_aspect

        try:
            width, height = self._document.page_display_size(0)
        except PDF_IO_ERRORS:
            return base_aspect
        if width <= 0 or height <= 0:
            return base_aspect
        return min(max(height / width, 0.5), 2.5)

    def _update_thumbnail_grid_size(self: _ThumbnailNavigationHost) -> None:
        """Scale the icon box and grid to fill the current pane width."""
        padding = self._thumbnail_cell_padding()
        if not self._thumbnail_list.isVisible():
            # Pre-layout geometry is meaningless; keep the base cell size
            # until the pane is shown and reports its real width.
            icon_size = QSize(_THUMBNAIL_ICON_SIZE)
            viewport_width = 0
        else:
            viewport_width = self._thumbnail_list.viewport().width()
            icon_width = max(
                viewport_width - padding.width(),
                _THUMBNAIL_ICON_SIZE.width(),
            )
            icon_size = QSize(
                icon_width,
                round(icon_width * self._thumbnail_page_aspect()),
            )
        grid_size = QSize(
            max(viewport_width, icon_size.width() + padding.width()),
            icon_size.height() + padding.height(),
        )
        icon_changed = icon_size != self._thumbnail_list.iconSize()
        if not icon_changed and grid_size == self._thumbnail_list.gridSize():
            return

        self._thumbnail_list.setIconSize(icon_size)
        self._thumbnail_list.setGridSize(grid_size)
        for row in range(self._thumbnail_list.count()):
            item = self._thumbnail_list.item(row)
            if item is not None:
                item.setSizeHint(grid_size)
        if icon_changed and self._thumbnail_rendered_pages:
            # Existing icons were rendered for the old size; re-render at
            # the new resolution once resize activity settles.
            self._thumbnail_rerender_timer.start()

    def _rerender_thumbnails(self: _ThumbnailNavigationHost) -> None:
        """Discard rendered thumbnails and re-render at the current size."""
        self._generations.thumbnail += 1
        self._thumbnail_rendered_pages.clear()
        self._thumbnail_pending_pages.clear()
        self._refresh_visible_thumbnails()
