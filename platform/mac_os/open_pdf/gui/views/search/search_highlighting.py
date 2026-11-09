"""Search highlighting behavior for pages and extracted text."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import QRectF
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import QTextEdit

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLineEdit

    from open_pdf.application.document.session import PdfDocument
    from open_pdf.domains.document.models import Rectangle


class _SearchHighlightHost(Protocol):
    """Describe the main-window API required by SearchHighlightMixin."""

    _document: PdfDocument
    _page_text: QTextEdit
    _search_input: QLineEdit

    def _highlight_text_matches(
        self,
        *,
        query: str,
    ) -> None: ...


class SearchHighlightMixin:
    """Apply visual search highlights to page images and text."""

    def _update_text_panel(self: _SearchHighlightHost) -> None:
        current_text = self._document.page_text()
        self._page_text.setPlainText(current_text)
        self._highlight_text_matches(query=self._search_input.text().strip())

    def _highlight_search_matches(
        self: _SearchHighlightHost,
        *,
        pixmap: QPixmap,
        rectangles: tuple[Rectangle, ...],
    ) -> QPixmap:
        if not rectangles:
            return pixmap

        highlighted = QPixmap(pixmap)
        painter = QPainter(highlighted)
        pen = QPen(QColor(255, 174, 0, 200))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 235, 59, 90))

        zoom = self._document.state.zoom
        for rectangle in rectangles:
            painter.drawRect(
                QRectF(
                    rectangle[0] * zoom,
                    rectangle[1] * zoom,
                    (rectangle[2] - rectangle[0]) * zoom,
                    (rectangle[3] - rectangle[1]) * zoom,
                ),
            )

        painter.end()
        return highlighted

    def _highlight_text_matches(
        self: _SearchHighlightHost,
        *,
        query: str,
    ) -> None:
        extra_selections: list[QTextEdit.ExtraSelection] = []
        if query:
            plain_text = self._page_text.toPlainText()
            lower_text = plain_text.lower()
            lower_query = query.lower()
            start_index = 0

            while True:
                match_index = lower_text.find(lower_query, start_index)
                if match_index < 0:
                    break

                selection = QTextEdit.ExtraSelection()
                selection_cursor = self._page_text.textCursor()
                selection_cursor.setPosition(match_index)
                selection_cursor.setPosition(
                    match_index + len(query),
                    QTextCursor.MoveMode.KeepAnchor,
                )

                selection_format = QTextCharFormat()
                selection_format.setBackground(QColor(255, 235, 59, 120))
                selection.cursor = selection_cursor
                selection.format = selection_format
                extra_selections.append(selection)
                start_index = match_index + len(query)

        self._page_text.setExtraSelections(extra_selections)
