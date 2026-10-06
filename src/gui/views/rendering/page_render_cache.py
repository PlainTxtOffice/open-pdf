"""Visible-page render queue and cache behavior."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from PySide6.QtGui import QImage, QPixmap

from src.adapters.document.pymupdf.qt import qimage_from_pymupdf
from src.domains.document.errors import PDF_IO_ERRORS
from src.gui.views.rendering.page_metrics import PAGE_CONTENT_CHROME
from src.gui.views.rendering.page_rendering import (
    PageRenderRequest,
    PageRenderTask,
)

if TYPE_CHECKING:
    from threading import Lock

    import pymupdf
    from PySide6.QtCore import QThreadPool
    from PySide6.QtWidgets import QLabel

    from src.domains.document.reader import PdfDocument
    from src.gui.models.window_state import RenderGenerations

logger = logging.getLogger(__name__)


class _PageRenderCacheHost(Protocol):
    """Describe the main-window API required by PageRenderCacheMixin."""

    _document: PdfDocument
    _page_labels: list[QLabel]
    _visible_page_indexes: list[int]
    _rendered_page_indexes: set[int]
    _pending_page_indexes: dict[int, int]
    _desired_page_indexes: set[int]
    _generations: RenderGenerations
    _render_request_counter: int
    _render_request_lock: Lock
    _render_scope_generation: int
    _render_scope_page_indexes: frozenset[int]
    _thread_pool: QThreadPool

    def _visible_label_range(self) -> tuple[int, int]: ...
    def _label_index_for_page(
        self,
        page_index: int | None,
    ) -> int | None: ...
    def _update_current_page_highlight(self) -> None: ...
    def _render_device_pixel_ratio(self) -> float: ...
    def _highlight_search_matches(
        self,
        *,
        pixmap: QPixmap,
        rectangles: tuple[pymupdf.Rect, ...],
    ) -> QPixmap: ...
    def _ensure_page_links_loaded(self, page_index: int) -> None: ...
    def _search_rectangles_for_page(
        self,
        page_index: int,
    ) -> tuple[pymupdf.Rect, ...]: ...
    def _ensure_page_words_loaded(self, page_index: int) -> None: ...
    def _evict_far_off_pages(self) -> None: ...

    def _handle_page_render_cancelled(
        self,
        _generation: int,
        page_index: int,
        request_token: int,
    ) -> None: ...

    def _handle_page_render_failed(
        self,
        generation: int,
        page_index: int,
        request_token: int | None,
        error_message: str,
    ) -> None: ...

    def _handle_page_rendered(
        self,
        generation: int,
        page_index: int,
        request_token: int | None,
        image: QImage,
    ) -> None: ...

    def _is_page_render_pending(
        self,
        page_index: int,
    ) -> bool: ...

    def _is_render_request_current(
        self,
        generation: int,
        page_index: int,
        request_token: int,
    ) -> bool: ...

    @staticmethod
    def _page_placeholder_text(page_index: int) -> str: ...

    def _pages_to_keep_cached(self) -> tuple[int, ...]: ...

    def _pages_to_render(self) -> tuple[int, ...]: ...

    def _queue_page_render(self, page_index: int) -> None: ...

    def _register_pending_page_render(
        self,
        page_index: int,
    ) -> int: ...

    def _render_dirty_page(self, page_index: int) -> None: ...

    def _retire_pending_page_render(
        self,
        page_index: int,
        request_token: int | None,
    ) -> None: ...

    def _sync_render_request_scope(self) -> None: ...


class PageRenderCacheMixin:
    """Manage visible page render requests and cached page pixmaps."""

    def _refresh_visible_pages(self: _PageRenderCacheHost) -> None:
        page_indexes_to_render = set(self._pages_to_render())
        self._desired_page_indexes = page_indexes_to_render
        self._sync_render_request_scope()
        self._evict_far_off_pages()

        for page_index in sorted(page_indexes_to_render):
            self._queue_page_render(page_index)

    def _pages_to_render(self: _PageRenderCacheHost) -> tuple[int, ...]:
        if not self._page_labels:
            return ()

        first_visible, last_visible = self._visible_label_range()
        preload_before = max(first_visible - 1, 0)
        preload_after = min(last_visible + 1, len(self._page_labels) - 1)
        return tuple(
            self._visible_page_indexes[label_index]
            for label_index in range(preload_before, preload_after + 1)
        )

    def _render_page_label(self: _PageRenderCacheHost, page_index: int) -> None:
        if page_index in self._rendered_page_indexes:
            return

        self._queue_page_render(page_index)

    def _queue_page_render(self: _PageRenderCacheHost, page_index: int) -> None:
        if page_index in self._rendered_page_indexes:
            return

        if self._is_page_render_pending(page_index):
            return

        if self._document.is_dirty():
            self._render_dirty_page(page_index)
            return

        source_path = self._document.source_path
        if source_path is None:
            return

        request_token = self._register_pending_page_render(page_index)
        task = PageRenderTask(
            request=PageRenderRequest(
                source_path=source_path,
                render_revision=self._document.render_revision,
                page_index=page_index,
                zoom=self._document.state.zoom,
                device_pixel_ratio=self._render_device_pixel_ratio(),
                generation=self._generations.render,
                request_token=request_token,
                is_still_current=self._is_render_request_current,
            ),
        )
        task.signals.rendered.connect(self._handle_page_rendered)
        task.signals.failed.connect(self._handle_page_render_failed)
        task.signals.cancelled.connect(self._handle_page_render_cancelled)
        self._thread_pool.start(task)

    def _sync_render_request_scope(self: _PageRenderCacheHost) -> None:
        with self._render_request_lock:
            self._render_scope_generation = self._generations.render
            self._render_scope_page_indexes = frozenset(
                self._desired_page_indexes,
            )

    def _reset_render_request_scope(self: _PageRenderCacheHost) -> None:
        with self._render_request_lock:
            self._render_scope_generation = self._generations.render
            self._render_scope_page_indexes = frozenset()
            self._pending_page_indexes.clear()

    def _is_page_render_pending(
        self: _PageRenderCacheHost,
        page_index: int,
    ) -> bool:
        with self._render_request_lock:
            return page_index in self._pending_page_indexes

    def _register_pending_page_render(
        self: _PageRenderCacheHost,
        page_index: int,
    ) -> int:
        with self._render_request_lock:
            self._render_request_counter += 1
            request_token = self._render_request_counter
            self._pending_page_indexes[page_index] = request_token
            return request_token

    def _is_render_request_current(
        self: _PageRenderCacheHost,
        generation: int,
        page_index: int,
        request_token: int,
    ) -> bool:
        with self._render_request_lock:
            return (
                generation == self._render_scope_generation
                and page_index in self._render_scope_page_indexes
                and self._pending_page_indexes.get(page_index) == request_token
            )

    def _retire_pending_page_render(
        self: _PageRenderCacheHost,
        page_index: int,
        request_token: int | None,
    ) -> None:
        if request_token is None:
            return

        with self._render_request_lock:
            if self._pending_page_indexes.get(page_index) != request_token:
                return
            del self._pending_page_indexes[page_index]

    def _handle_page_rendered(
        self: _PageRenderCacheHost,
        generation: int,
        page_index: int,
        request_token: int | None,
        image: QImage,
    ) -> None:
        self._retire_pending_page_render(page_index, request_token)
        if generation != self._generations.render:
            return

        if page_index not in self._desired_page_indexes:
            return

        page_pixmap = QPixmap.fromImage(image)
        highlighted_pixmap = self._highlight_search_matches(
            pixmap=page_pixmap,
            rectangles=self._search_rectangles_for_page(page_index),
        )

        label_index = self._label_index_for_page(page_index)
        if label_index is None:
            return

        page_label = self._page_labels[label_index]
        page_label.setPixmap(highlighted_pixmap)
        page_label.setText("")
        logical_size = highlighted_pixmap.deviceIndependentSize()
        page_label.setFixedSize(
            round(logical_size.width()) + PAGE_CONTENT_CHROME,
            round(logical_size.height()) + PAGE_CONTENT_CHROME,
        )
        self._rendered_page_indexes.add(page_index)
        self._ensure_page_links_loaded(page_index)
        self._ensure_page_words_loaded(page_index)
        self._update_current_page_highlight()

    def _handle_page_render_failed(
        self: _PageRenderCacheHost,
        generation: int,
        page_index: int,
        request_token: int | None,
        error_message: str,
    ) -> None:
        self._retire_pending_page_render(page_index, request_token)
        if generation != self._generations.render:
            return

        label_index = self._label_index_for_page(page_index)
        if label_index is None:
            return

        page_label = self._page_labels[label_index]
        page_label.setText(
            f"Failed to render page {page_index + 1}\n{error_message}",
        )

    def _handle_page_render_cancelled(
        self: _PageRenderCacheHost,
        _generation: int,
        page_index: int,
        request_token: int,
    ) -> None:
        self._retire_pending_page_render(page_index, request_token)

    def _render_dirty_page(self: _PageRenderCacheHost, page_index: int) -> None:
        try:
            device_pixel_ratio = self._render_device_pixel_ratio()
            image = qimage_from_pymupdf(
                self._document.render_page(
                    page_index,
                    device_pixel_ratio=device_pixel_ratio,
                ),
            )
            image.setDevicePixelRatio(device_pixel_ratio)
        except PDF_IO_ERRORS as error:
            logger.exception(
                "Failed to render dirty page %d",
                page_index + 1,
            )
            self._handle_page_render_failed(
                self._generations.render,
                page_index,
                None,
                str(error),
            )
            return

        self._handle_page_rendered(
            self._generations.render,
            page_index,
            None,
            image,
        )

    def _evict_far_off_pages(self: _PageRenderCacheHost) -> None:
        keep_page_indexes = set(self._pages_to_keep_cached())
        page_indexes_to_evict = self._rendered_page_indexes - keep_page_indexes
        for page_index in sorted(page_indexes_to_evict):
            label_index = self._label_index_for_page(page_index)
            if label_index is None:
                continue

            page_label = self._page_labels[label_index]
            page_label.setPixmap(QPixmap())
            page_label.setText(self._page_placeholder_text(page_index))
            self._rendered_page_indexes.discard(page_index)

    def _pages_to_keep_cached(self: _PageRenderCacheHost) -> tuple[int, ...]:
        if not self._page_labels:
            return ()

        first_visible, last_visible = self._visible_label_range()
        preload_before = max(first_visible - 3, 0)
        preload_after = min(last_visible + 3, len(self._page_labels) - 1)
        return tuple(
            self._visible_page_indexes[label_index]
            for label_index in range(preload_before, preload_after + 1)
        )

    @staticmethod
    def _page_placeholder_text(page_index: int) -> str:
        return f"Loading page {page_index + 1}..."
