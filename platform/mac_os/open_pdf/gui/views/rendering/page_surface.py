"""Page surface widgets that combine rendered page images with text overlays."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QResizeEvent,
)
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QMenu, QWidget

from open_pdf.gui.views.rendering.page_metrics import PAGE_CONTENT_CHROME

if TYPE_CHECKING:
    from collections.abc import Sequence

    from open_pdf.domains.document.models import PdfPageLink

_SELECTION_COLOR = QColor(53, 132, 228, 110)
_HITBOX_PADDING = 2.0


@dataclass(frozen=True)
class _OverlayWord:
    rect: QRectF
    page_rect: tuple[float, float, float, float]
    text: str
    block_index: int
    line_index: int
    word_index: int


@dataclass(frozen=True)
class _SurfaceLink:
    rect: QRectF
    link: PdfPageLink


class PageTextOverlay(QFrame):
    """Transparent widget that selects text using exact PDF word boxes."""

    link_activation_requested = Signal(QPointF)
    link_hover_requested = Signal(QPointF)
    link_hover_cleared = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the transparent overlay widget."""
        super().__init__(parent)
        self._words: list[_OverlayWord] = []
        self._page_zoom = 1.0
        self._selection_anchor: int | None = None
        self._selection_start: int | None = None
        self._selection_end: int | None = None
        self._drag_active = False
        self._selection_press_position: QPointF | None = None
        self._selection_dragged = False
        self._edit_selection_enabled = False
        self._edit_drag_origin: QPointF | None = None
        self._edit_selection_rect: QRectF | None = None
        self._interaction_flags = Qt.TextInteractionFlag.NoTextInteraction
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.hide()

    def viewport(self) -> QWidget:
        """Mirror QTextEdit's viewport API used by host context-menu code."""
        return self

    def set_words(
        self,
        words: Sequence[tuple[float, float, float, float, str, int, int, int]],
        *,
        zoom: float,
    ) -> None:
        """Load word boxes scaled into the current page render space."""
        self._page_zoom = max(zoom, 0.001)
        self._words = [
            _OverlayWord(
                rect=QRectF(
                    x0 * zoom,
                    y0 * zoom,
                    max((x1 - x0) * zoom, 1.0),
                    max((y1 - y0) * zoom, 1.0),
                ),
                page_rect=(x0, y0, x1, y1),
                text=text,
                block_index=block_index,
                line_index=line_index,
                word_index=word_index,
            )
            for x0, y0, x1, y1, text, block_index, line_index, word_index in words  # noqa: E501
            if text.strip()
        ]
        self.clear_selection()

    def set_page_zoom(self, *, zoom: float) -> None:
        """Store the current zoom used for edit-rectangle mapping."""
        self._page_zoom = max(zoom, 0.001)

    def setTextInteractionFlags(  # noqa: N802
        self,
        flags: Qt.TextInteractionFlag,
    ) -> None:
        """Match the QTextEdit-style API expected by the caller."""
        self._interaction_flags = flags
        if not self._selection_enabled():
            self.clear_selection()

    def textInteractionFlags(self) -> Qt.TextInteractionFlag:  # noqa: N802
        """Return the current selection-interaction flags."""
        return self._interaction_flags

    def selectedText(self) -> str:  # noqa: N802
        """Match the QTextCursor-style selected text helper."""
        return self.selected_text()

    def selected_text(self) -> str:
        """Return the selected words in reading order."""
        selected_indexes = self._selected_indexes()
        if not selected_indexes:
            return ""

        parts: list[str] = []
        previous_word: _OverlayWord | None = None
        for word_index in selected_indexes:
            word = self._words[word_index]
            if previous_word is not None:
                if (
                    word.block_index != previous_word.block_index
                    or word.line_index != previous_word.line_index
                ):
                    parts.append("\n")
                else:
                    parts.append(" ")
            parts.append(word.text)
            previous_word = word

        return "".join(parts)

    def selected_word_rectangles(
        self,
    ) -> list[tuple[float, float, float, float]]:
        """Return the selected word boxes in original PDF page coordinates."""
        return [
            self._words[word_index].page_rect
            for word_index in self._selected_indexes()
        ]

    def selected_region_rectangle(
        self,
    ) -> tuple[float, float, float, float] | None:
        """Return the selected edit rectangle in original PDF coordinates."""
        if (
            self._edit_selection_rect is None
            or self._edit_selection_rect.isEmpty()
        ):
            return None

        normalized_rect = self._edit_selection_rect.normalized()
        zoom = max(self._page_zoom, 0.001)
        return (
            normalized_rect.left() / zoom,
            normalized_rect.top() / zoom,
            normalized_rect.right() / zoom,
            normalized_rect.bottom() / zoom,
        )

    def select_region_rectangle(
        self,
        page_rect: tuple[float, float, float, float],
    ) -> None:
        """Select one rectangular page region for edit-mode redaction."""
        x0, y0, x1, y1 = page_rect
        zoom = max(self._page_zoom, 0.001)
        self._selection_anchor = None
        self._selection_start = None
        self._selection_end = None
        self._edit_selection_rect = QRectF(
            QPointF(x0 * zoom, y0 * zoom),
            QPointF(x1 * zoom, y1 * zoom),
        ).normalized()
        self.update()

    def set_edit_selection_enabled(self, *, enabled: bool) -> None:
        """Toggle whether drag-to-select rectangle editing is enabled."""
        self._edit_selection_enabled = enabled
        if not enabled:
            self._edit_drag_origin = None
            self._edit_selection_rect = None
            self.update()

    def select_word_range(self, start_index: int, end_index: int) -> None:
        """Select an inclusive word range for tests and programmatic flows."""
        if not self._words:
            self.clear_selection()
            return

        lower_bound = max(min(start_index, end_index), 0)
        upper_bound = min(max(start_index, end_index), len(self._words) - 1)
        self._selection_anchor = lower_bound
        self._selection_start = lower_bound
        self._selection_end = upper_bound
        self.update()

    def selectAll(self) -> None:  # noqa: N802
        """Select all extracted words."""
        if not self._words:
            self.clear_selection()
            return

        self._selection_anchor = 0
        self._selection_start = 0
        self._selection_end = len(self._words) - 1
        self.update()

    def clear_selection(self) -> None:
        """Clear the current word selection."""
        self._selection_anchor = None
        self._selection_start = None
        self._selection_end = None
        self._drag_active = False
        self._selection_press_position = None
        self._selection_dragged = False
        self._edit_drag_origin = None
        self._edit_selection_rect = None
        self.update()

    def createStandardContextMenu(self) -> QMenu:  # noqa: N802
        """Provide explicit actions instead of relying on QTextBrowser."""
        menu = QMenu(self)
        selected_text = self.selected_text()

        copy_action = QAction("Copy", menu)
        copy_action.setEnabled(bool(selected_text))
        copy_action.triggered.connect(self._copy_selection)
        menu.addAction(copy_action)

        select_all_action = QAction("Select All", menu)
        select_all_action.setEnabled(bool(self._words))
        select_all_action.triggered.connect(self.selectAll)
        menu.addAction(select_all_action)

        return menu

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Handle mouse clicks to start word selection."""
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._edit_selection_enabled
        ):
            self._selection_anchor = None
            self._selection_start = None
            self._selection_end = None
            self._edit_drag_origin = event.position()
            self._edit_selection_rect = QRectF(
                self._edit_drag_origin,
                self._edit_drag_origin,
            )
            self.update()
            event.accept()
            return

        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._selection_enabled()
        ):
            word_index = self._word_index_at(event.position())
            if word_index is None:
                self.clear_selection()
            else:
                self._selection_anchor = word_index
                self._selection_start = word_index
                self._selection_end = word_index
                self.update()
            self._drag_active = True
            self._selection_press_position = event.position()
            self._selection_dragged = False
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Update the word selection range during a mouse drag."""
        if self._edit_drag_origin is not None and self._edit_selection_enabled:
            self.link_hover_cleared.emit()
            self._edit_selection_rect = QRectF(
                self._edit_drag_origin,
                event.position(),
            ).normalized()
            self.update()
            event.accept()
            return

        if self._drag_active:
            press_position = self._selection_press_position
            if (
                press_position is not None
                and (event.position() - press_position).manhattanLength()
                >= QApplication.startDragDistance()
            ):
                self._selection_dragged = True

        if self._drag_active and self._selection_anchor is not None:
            self.link_hover_cleared.emit()
            word_index = self._word_index_at(event.position())
            if word_index is None:
                word_index = self._nearest_word_index(event.position())
            if word_index is not None:
                self._selection_start = min(self._selection_anchor, word_index)
                self._selection_end = max(self._selection_anchor, word_index)
                self.update()
            event.accept()
            return

        if self._edit_selection_enabled:
            self.link_hover_cleared.emit()
        else:
            self.link_hover_requested.emit(event.position())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # pyright: ignore[reportMissingParameterType] # noqa: ANN001, N802
        """Clear link feedback when the pointer leaves the text overlay."""
        self.link_hover_cleared.emit()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Finish the word selection on mouse release."""
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._edit_drag_origin is not None
            and self._edit_selection_enabled
        ):
            self._edit_drag_origin = None
            if self._edit_selection_rect is not None:
                normalized_rect = self._edit_selection_rect.normalized()
                if normalized_rect.width() < 1 or normalized_rect.height() < 1:
                    self._edit_selection_rect = None
            self.update()
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self._drag_active:
            self._drag_active = False
            if not self._selection_dragged:
                self.link_activation_requested.emit(event.position())
            self._selection_press_position = None
            self._selection_dragged = False
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Draw the semi-transparent selection boxes over selected words."""
        super().paintEvent(event)
        selected_indexes = self._selected_indexes()
        if not selected_indexes and self._edit_selection_rect is None:
            return

        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_SELECTION_COLOR)
        for word_index in selected_indexes:
            painter.drawRect(self._words[word_index].rect)

        if self._edit_selection_rect is not None:
            painter.setBrush(QColor(53, 132, 228, 40))
            painter.setPen(QColor(53, 132, 228, 180))
            painter.drawRect(self._edit_selection_rect)
        painter.end()

    def _copy_selection(self) -> None:
        selected_text = self.selected_text()
        if not selected_text:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(selected_text)

    def _selection_enabled(self) -> bool:
        return bool(
            self._interaction_flags
            & Qt.TextInteractionFlag.TextSelectableByMouse,
        )

    def _selected_indexes(self) -> list[int]:
        if self._selection_start is None or self._selection_end is None:
            return []

        return list(range(self._selection_start, self._selection_end + 1))

    def _word_index_at(self, position: QPointF) -> int | None:
        for word_index, word in enumerate(self._words):
            if word.rect.adjusted(
                -_HITBOX_PADDING,
                -_HITBOX_PADDING,
                _HITBOX_PADDING,
                _HITBOX_PADDING,
            ).contains(position):
                return word_index

        return None

    def _nearest_word_index(self, position: QPointF) -> int | None:
        if not self._words:
            return None

        nearest_index: int | None = None
        nearest_distance: float | None = None
        for word_index, word in enumerate(self._words):
            center = word.rect.center()
            distance = abs(center.x() - position.x()) + abs(
                center.y() - position.y(),
            )
            if nearest_distance is None or distance < nearest_distance:
                nearest_index = word_index
                nearest_distance = distance

        return nearest_index


class PageSurfaceLabel(QLabel):
    """Render one page pixmap and optionally expose a selectable text layer."""

    link_activated = Signal(object)

    def __init__(self) -> None:
        """Initialize the page surface widget."""
        super().__init__()
        self._text_layer = PageTextOverlay(self)
        self._text_layer.link_activation_requested.connect(
            self._activate_link_at,
        )
        self._text_layer.link_hover_requested.connect(
            self._update_overlay_link_hover,
        )
        self._text_layer.link_hover_cleared.connect(self._clear_link_hover)
        self._page_links: list[_SurfaceLink] = []
        self._hovered_link: _SurfaceLink | None = None
        self._text_layer.hide()
        self.setMouseTracking(True)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Resize the text layer to match the page surface."""
        super().resizeEvent(event)
        self._layout_text_layer()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint the page and underline the link currently under the pointer."""
        super().paintEvent(event)
        if self._hovered_link is None:
            return

        inset = PAGE_CONTENT_CHROME / 2
        link_rect = self._hovered_link.rect.translated(inset, inset)
        underline_y = link_rect.bottom() - 1.0
        painter = QPainter(self)
        painter.setPen(
            QPen(
                self.palette().color(QPalette.ColorRole.Link),
                1.5,
            ),
        )
        painter.drawLine(
            QPointF(link_rect.left(), underline_y),
            QPointF(link_rect.right(), underline_y),
        )
        painter.end()

    def text_layer(self) -> PageTextOverlay:
        """Return the child widget that hosts the selectable text overlay."""
        return self._text_layer

    def set_page_text_words(
        self,
        words: Sequence[tuple[float, float, float, float, str, int, int, int]],
        *,
        zoom: float,
    ) -> None:
        """Set the word-based text overlay for one page at the current zoom."""
        self._text_layer.set_words(words, zoom=zoom)
        self._layout_text_layer()

    def set_page_zoom(self, *, zoom: float) -> None:
        """Update the zoom used by the overlay's edit-rectangle mapping."""
        self._text_layer.set_page_zoom(zoom=zoom)

    def set_page_links(
        self,
        links: Sequence[PdfPageLink],
    ) -> None:
        """Set clickable link hotspots for one rendered page."""
        self._page_links = [
            _SurfaceLink(
                rect=QRectF(
                    x0,
                    y0,
                    max(x1 - x0, 1.0),
                    max(y1 - y0, 1.0),
                ),
                link=link,
            )
            for link in links
            for x0, y0, x1, y1 in [link.bounds]
        ]
        self._clear_link_hover()

    def set_text_selection_enabled(self, *, enabled: bool) -> None:
        """Toggle whether the overlaid text layer accepts mouse selection."""
        self._text_layer.set_edit_selection_enabled(enabled=False)
        if enabled:
            interaction_flags = (
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
            self._text_layer.setTextInteractionFlags(interaction_flags)
            self._text_layer.show()
            self._text_layer.raise_()
            self._clear_link_hover()
            return

        self._text_layer.clear_selection()
        self._text_layer.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction,
        )
        self._text_layer.hide()
        self._clear_link_hover()

    def set_edit_selection_enabled(self, *, enabled: bool) -> None:
        """Toggle whether the overlaid text layer accepts rectangle edits."""
        if enabled:
            self._text_layer.clear_selection()
            self._text_layer.setTextInteractionFlags(
                Qt.TextInteractionFlag.NoTextInteraction,
            )
            self._text_layer.set_edit_selection_enabled(enabled=True)
            self._text_layer.show()
            self._text_layer.raise_()
            self._clear_link_hover()
            return

        self._text_layer.set_edit_selection_enabled(enabled=False)
        self._text_layer.hide()
        self._clear_link_hover()

    def selected_text(self) -> str:
        """Return the currently selected text from the overlay."""
        return self._text_layer.selected_text()

    def selected_word_rectangles(
        self,
    ) -> list[tuple[float, float, float, float]]:
        """Return the selected overlay word boxes in PDF page coordinates."""
        return self._text_layer.selected_word_rectangles()

    def selected_redaction_rectangles(
        self,
    ) -> list[tuple[float, float, float, float]]:
        """Return the currently selected page regions for removal."""
        region_rectangle = self._text_layer.selected_region_rectangle()
        if region_rectangle is not None:
            return [region_rectangle]

        return self._text_layer.selected_word_rectangles()

    def select_region_rectangle(
        self,
        page_rect: tuple[float, float, float, float],
    ) -> None:
        """Programmatically select one rectangular page region."""
        self._text_layer.select_region_rectangle(page_rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Activate a page link when the browse surface is clicked."""
        if event.button() == Qt.MouseButton.LeftButton:
            active_link = self._link_at(event.position())
            if active_link is not None:
                self.link_activated.emit(active_link)
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Show link feedback when the browse surface is over a page link."""
        self._update_link_hover(event.position())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # pyright: ignore[reportMissingParameterType] # noqa: ANN001, N802
        """Clear link feedback after leaving the page surface."""
        self._clear_link_hover()
        super().leaveEvent(event)

    def _layout_text_layer(self) -> None:
        inset = PAGE_CONTENT_CHROME // 2
        self._text_layer.setGeometry(
            inset,
            inset,
            max(self.width() - PAGE_CONTENT_CHROME, 0),
            max(self.height() - PAGE_CONTENT_CHROME, 0),
        )

    def _link_at(self, position: QPointF) -> PdfPageLink | None:
        content_position = self._content_position(position)
        if content_position is None:
            return None

        surface_link = self._surface_link_at(content_position)
        return None if surface_link is None else surface_link.link

    def _surface_link_at(
        self,
        content_position: QPointF,
    ) -> _SurfaceLink | None:
        for surface_link in self._page_links:
            if surface_link.rect.contains(content_position):
                return surface_link

        return None

    def _activate_link_at(self, content_position: QPointF) -> None:
        for surface_link in self._page_links:
            if surface_link.rect.contains(content_position):
                self.link_activated.emit(surface_link.link)
                return

    def _content_position(self, position: QPointF) -> QPointF | None:
        inset = PAGE_CONTENT_CHROME / 2
        content_position = QPointF(position.x() - inset, position.y() - inset)
        if content_position.x() < 0 or content_position.y() < 0:
            return None

        return content_position

    def _update_overlay_link_hover(self, content_position: QPointF) -> None:
        self._set_hovered_link(self._surface_link_at(content_position))

    def _update_link_hover(self, position: QPointF) -> None:
        content_position = self._content_position(position)
        hovered_link = (
            None
            if content_position is None
            else self._surface_link_at(content_position)
        )
        self._set_hovered_link(hovered_link)

    def _clear_link_hover(self) -> None:
        self._set_hovered_link(None)

    def _set_hovered_link(self, hovered_link: _SurfaceLink | None) -> None:
        if hovered_link != self._hovered_link:
            self._hovered_link = hovered_link
            self.update()

        cursor_widget = (
            self._text_layer if self._text_layer.isVisible() else self
        )
        inactive_widget = (
            self if cursor_widget is self._text_layer else self._text_layer
        )
        inactive_widget.unsetCursor()
        if hovered_link is None:
            cursor_widget.unsetCursor()
            return

        cursor_widget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
