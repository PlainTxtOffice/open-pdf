"""Per-thread PyMuPDF document handle cache for background renders."""

from __future__ import annotations

import threading
from contextlib import suppress
from typing import TYPE_CHECKING

import pymupdf

if TYPE_CHECKING:
    from pathlib import Path


class _RenderHandleCache:
    """Reuse one open document per worker thread, keyed by source path."""

    def __init__(self) -> None:
        """Initialize the per-thread store and the shared handle registry."""
        self._local = threading.local()
        self._lock = threading.Lock()
        self._open_handles: dict[int, pymupdf.Document] = {}
        self._epoch = 0

    def acquire(
        self,
        source_path: Path,
        render_revision: int,
    ) -> pymupdf.Document:
        """Return an open document for `source_path` on the current thread.

        - Reuses the existing handle when its path matches.
        - Closes the previous handle and opens a fresh one when the path,
          render revision, or close-all epoch differs.
        """
        existing: pymupdf.Document | None = getattr(self._local, "handle", None)
        existing_path: Path | None = getattr(self._local, "source_path", None)
        existing_revision: int | None = getattr(
            self._local,
            "render_revision",
            None,
        )
        existing_epoch: int | None = getattr(self._local, "epoch", None)

        with self._lock:
            current_epoch = self._epoch
            handle_is_current = existing is not None and (
                existing_epoch == current_epoch
            )
            if (
                existing is not None
                and existing_epoch == current_epoch
                and existing_path == source_path
                and existing_revision == render_revision
            ):
                return existing

            if handle_is_current:
                self._open_handles.pop(threading.get_ident(), None)

        if handle_is_current and existing is not None:
            existing.close()

        handle = pymupdf.open(source_path)
        self._local.handle = handle
        self._local.source_path = source_path
        self._local.render_revision = render_revision
        with self._lock:
            self._local.epoch = self._epoch
            self._open_handles[threading.get_ident()] = handle
        return handle

    def invalidate(self) -> None:
        """Close and forget the current thread's cached handle."""
        existing: pymupdf.Document | None = getattr(self._local, "handle", None)
        existing_epoch: int | None = getattr(self._local, "epoch", None)
        with self._lock:
            handle_is_current = existing is not None and (
                existing_epoch == self._epoch
            )
            self._open_handles.pop(threading.get_ident(), None)
        if handle_is_current and existing is not None:
            existing.close()
        self._local.handle = None
        self._local.source_path = None
        self._local.render_revision = None
        self._local.epoch = None

    def close_all(self) -> None:
        """Close every cached handle across all threads.

        Callers must ensure no render task is mid-render, e.g. by waiting
        for the render thread pool to drain first.
        """
        with self._lock:
            self._epoch += 1
            handles = list(self._open_handles.values())
            self._open_handles.clear()

        for handle in handles:
            with suppress(ValueError, RuntimeError):
                handle.close()


RENDER_HANDLE_CACHE = _RenderHandleCache()
