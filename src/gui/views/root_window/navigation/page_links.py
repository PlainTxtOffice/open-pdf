"""Presentation behavior for links embedded in PDF pages."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from src.domains.document.errors import PDF_IO_ERRORS
from src.gui.views.rendering.page_surface import PageSurfaceLabel

if TYPE_CHECKING:
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QLabel

    from src.domains.document.models import PdfPageLink
    from src.domains.document.reader import PdfDocument


logger = logging.getLogger(__name__)

_WINDOWS_DRIVE_PREFIX_LENGTH = 2
_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


class PageLinkNavigationMixin:
    """Load, resolve, and activate links from rendered PDF pages."""

    if TYPE_CHECKING:
        _document: PdfDocument
        _page_labels: list[QLabel]

        def _label_index_for_page(
            self,
            page_index: int | None,
        ) -> int | None: ...
        def _apply_zoom(
            self,
            target_zoom: float,
            *,
            anchor_position: QPointF | None = None,
        ) -> None: ...
        def _sync_current_page_ui(self, *, scroll_to_page: bool) -> None: ...
        def _scroll_to_page_position(
            self,
            *,
            page_index: int,
            position: tuple[float, float] | None,
        ) -> None: ...
        def _show_error(self, message: str) -> None: ...
        def open_document_in_tab(self, path: Path) -> None:
            """Open the given PDF file in a new document tab."""
            ...

    def _ensure_page_links_loaded(self, page_index: int) -> None:
        """Load link hotspots for one visible page."""
        label_index = self._label_index_for_page(page_index)
        if label_index is None:
            return
        page_label = self._page_labels[label_index]
        if not isinstance(page_label, PageSurfaceLabel):
            return
        try:
            page_label.set_page_links(self._document.page_links(page_index))
        except PDF_IO_ERRORS:
            logger.exception(
                "Failed to load page links for page %d",
                page_index + 1,
            )
            page_label.set_page_links([])

    def _handle_page_link_activated(self, link: PdfPageLink) -> None:
        """Open an external link or navigate to an internal target page."""
        target = None
        if link.uri is None and link.file_path is None:
            self._apply_page_link_zoom(link)
            target = self._document.resolve_page_link_target(
                target_page_index=link.target_page_index,
                target_point=link.target_point,
                named_destination=link.named_destination,
            )
        if target is not None:
            self._navigate_to_page_link_target(target)
            return
        if link.uri is not None:
            QDesktopServices.openUrl(QUrl.fromUserInput(link.uri))
            return
        if link.file_path is not None:
            self._open_page_link_file_target(link)

    def _apply_page_link_zoom(self, link: PdfPageLink) -> None:
        if link.target_zoom is not None:
            self._apply_zoom(link.target_zoom)

    def _navigate_to_page_link_target(
        self,
        target: tuple[int, tuple[float, float] | None],
    ) -> None:
        target_page_index, target_position = target
        self._document.go_to_page(target_page_index)
        self._sync_current_page_ui(scroll_to_page=False)
        self._scroll_to_page_position(
            page_index=target_page_index,
            position=target_position,
        )

    def _open_page_link_file_target(self, link: PdfPageLink) -> None:
        if link.file_path is None:
            return
        target_path = self._resolved_page_link_file_path(link.file_path)
        if target_path is None:
            return
        if not target_path.exists():
            self._show_error(f"Linked file not found:\n{target_path}")
            return
        if target_path.suffix.casefold() == ".pdf":
            self.open_document_in_tab(target_path)
            if self._document.source_path != target_path:
                return
            self._apply_page_link_zoom(link)
            target = self._document.resolve_page_link_target(
                target_page_index=link.target_page_index,
                target_point=link.target_point,
                named_destination=link.named_destination,
            )
            if target is not None:
                self._navigate_to_page_link_target(target)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target_path)))

    def _resolved_page_link_file_path(self, raw_path: str) -> Path | None:
        stripped_path = raw_path.strip()
        if not stripped_path:
            return None
        if self._has_unsupported_page_link_scheme(stripped_path):
            logger.warning("Ignoring non-local PDF file link: %s", raw_path)
            return None
        if stripped_path.casefold().startswith("file:"):
            target_url = QUrl(stripped_path)
            local_file = target_url.toLocalFile()
            if not local_file:
                logger.warning(
                    "Ignoring invalid file URL in PDF link: %s",
                    raw_path,
                )
                return None
            target_path = Path(local_file)
        else:
            target_path = Path(unquote(stripped_path))
        source_path = self._document.source_path
        if not target_path.is_absolute():
            if source_path is None:
                return None
            target_path = source_path.parent / target_path
        try:
            return target_path.expanduser().resolve(strict=False)
        except OSError:
            logger.warning(
                "Ignoring invalid PDF file link target: %s",
                raw_path,
            )
            return None

    @staticmethod
    def _has_unsupported_page_link_scheme(path_text: str) -> bool:
        scheme_match = _URI_SCHEME_RE.match(path_text)
        if scheme_match is None:
            return False
        if (
            len(path_text) >= _WINDOWS_DRIVE_PREFIX_LENGTH
            and path_text[1] == ":"
            and path_text[0].isalpha()
        ):
            return False
        return not path_text.casefold().startswith("file:")
