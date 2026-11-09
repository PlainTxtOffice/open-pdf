"""Present text replacement and redaction workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QInputDialog,
    QLabel,
    QWidget,
)

from open_pdf.adapters.document.errors import PDF_IO_ERRORS
from open_pdf.gui.views.rendering.page_surface import PageSurfaceLabel

if TYPE_CHECKING:
    from PySide6.QtWidgets import QScrollArea, QStatusBar

    from open_pdf.application.document.session import PdfDocument
    from open_pdf.domains.document.models import (
        PdfTextSpan,
    )
    from open_pdf.gui.models.window_state import SyncGuards


class _TextEditingHost(Protocol):
    """Describe the window operations required by this workflow."""

    _document: PdfDocument

    _page_labels: list[QLabel]

    _visible_page_indexes: list[int]

    _document_scroll_area: QScrollArea

    _sync: SyncGuards

    def _refresh_actions(self) -> None: ...

    def _clear_search_results(self) -> None: ...

    def _populate_thumbnails(self) -> None: ...

    def _refresh_document_view(
        self,
        *,
        scroll_to_page: bool,
    ) -> None: ...

    def _refresh_visible_pages(self) -> None: ...

    def _show_error(self, message: str) -> None: ...

    def statusBar(self) -> QStatusBar: ...  # noqa: N802

    def _label_index_for_page(
        self,
        page_index: int | None,
    ) -> int | None: ...

    def _apply_text_span_replacement(
        self,
        *,
        span: PdfTextSpan,
        replacement: str,
    ) -> None: ...

    def _resolve_redaction_target(
        self,
        *,
        page_index: int | None,
        page_label: PageSurfaceLabel | None,
    ) -> tuple[int, PageSurfaceLabel] | None: ...

    def _restore_document_scroll_position(
        self,
        *,
        horizontal_value: int,
        vertical_value: int,
    ) -> None: ...

    def _selected_page_surface_with_redaction(
        self,
    ) -> tuple[int, PageSurfaceLabel] | None: ...


class TextEditingMixin:
    """Coordinate text editing dialogs."""

    def _remove_selected_text(
        self: _TextEditingHost,
        *,
        page_index: int | None = None,
        page_label: PageSurfaceLabel | None = None,
    ) -> None:
        """Redact the current page-overlay word selection from the PDF."""
        if not self._document.has_document():
            return

        redaction_target = self._resolve_redaction_target(
            page_index=page_index,
            page_label=page_label,
        )
        if redaction_target is None:
            self._show_error(
                "Select a page region in Edit PDF mode, or select text first.",
            )
            return

        target_page_index, current_page_label = redaction_target
        selected_rectangles = current_page_label.selected_redaction_rectangles()
        if not selected_rectangles:
            self._show_error(
                "Select a page region in Edit PDF mode, or select text first.",
            )
            return

        horizontal_value = (
            self._document_scroll_area.horizontalScrollBar().value()
        )
        vertical_value = self._document_scroll_area.verticalScrollBar().value()

        try:
            changed = self._document.redact_text_rectangles(
                page_index=target_page_index,
                rectangles=selected_rectangles,
            )
        except PDF_IO_ERRORS as error:
            self._show_error(
                f"Failed to remove selected text:\n{error}",
            )
            return

        if not changed:
            self._show_error(
                "The selected text could not be removed.",
            )
            return

        if self._document.state.current_page_index != target_page_index:
            self._document.go_to_page(
                target_page_index,
                record_history=False,
            )

        self._clear_search_results()
        self._populate_thumbnails()
        self._refresh_document_view(scroll_to_page=False)
        QTimer.singleShot(
            0,
            lambda: self._restore_document_scroll_position(
                horizontal_value=horizontal_value,
                vertical_value=vertical_value,
            ),
        )
        self._refresh_actions()
        self.statusBar().showMessage("Removed content.", 5000)

    def _replace_selected_text(
        self: _TextEditingHost,
        *,
        page_index: int | None = None,
        page_label: PageSurfaceLabel | None = None,
    ) -> None:
        """Rewrite the text span the current page selection covers."""
        if not self._document.has_document():
            return

        target = self._resolve_redaction_target(
            page_index=page_index,
            page_label=page_label,
        )
        if target is None:
            self._show_error(
                "Select the text to replace in Edit PDF mode first.",
            )
            return

        target_page_index, current_page_label = target
        selected_rectangles = current_page_label.selected_redaction_rectangles()
        span = (
            self._document.span_for_rectangles(
                page_index=target_page_index,
                rectangles=selected_rectangles,
            )
            if selected_rectangles
            else None
        )
        if span is None:
            self._show_error(
                "No editable text was found in the selection.",
            )
            return

        replacement, accepted = QInputDialog.getText(
            cast("QWidget", self),
            "Replace Text",
            "Replacement text:",
            text=span.text,
        )
        if not accepted:
            return

        self._apply_text_span_replacement(span=span, replacement=replacement)

    def _apply_text_span_replacement(
        self: _TextEditingHost,
        *,
        span: PdfTextSpan,
        replacement: str,
    ) -> None:
        """Write one span replacement and refresh the affected views."""
        horizontal_value = (
            self._document_scroll_area.horizontalScrollBar().value()
        )
        vertical_value = self._document_scroll_area.verticalScrollBar().value()

        try:
            changed = self._document.replace_text_span(
                span=span,
                text=replacement,
            )
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to replace text:\n{error}")
            return

        if not changed:
            return

        if self._document.state.current_page_index != span.page_index:
            self._document.go_to_page(span.page_index, record_history=False)

        self._clear_search_results()
        self._populate_thumbnails()
        self._refresh_document_view(scroll_to_page=False)
        QTimer.singleShot(
            0,
            lambda: self._restore_document_scroll_position(
                horizontal_value=horizontal_value,
                vertical_value=vertical_value,
            ),
        )
        self._refresh_actions()
        self.statusBar().showMessage("Replaced text.", 5000)

    def _resolve_redaction_target(
        self: _TextEditingHost,
        *,
        page_index: int | None,
        page_label: PageSurfaceLabel | None,
    ) -> tuple[int, PageSurfaceLabel] | None:
        if page_index is None and page_label is None:
            selected_surface = self._selected_page_surface_with_redaction()
            if selected_surface is not None:
                return selected_surface

        target_page_index = (
            self._document.state.current_page_index
            if page_index is None
            else page_index
        )
        if page_label is not None:
            return target_page_index, page_label

        label_index = self._label_index_for_page(target_page_index)
        if label_index is None:
            return None

        candidate_label = self._page_labels[label_index]
        if not isinstance(candidate_label, PageSurfaceLabel):
            return None
        return target_page_index, candidate_label

    def _restore_document_scroll_position(
        self: _TextEditingHost,
        *,
        horizontal_value: int,
        vertical_value: int,
    ) -> None:
        """Restore the exact viewport scroll position after a rerender."""
        horizontal_bar = self._document_scroll_area.horizontalScrollBar()
        vertical_bar = self._document_scroll_area.verticalScrollBar()
        self._sync.scroll_position = True
        horizontal_bar.setValue(min(horizontal_value, horizontal_bar.maximum()))
        vertical_bar.setValue(min(vertical_value, vertical_bar.maximum()))
        self._sync.scroll_position = False
        self._document_scroll_area.viewport().update()
        self._refresh_visible_pages()

    def _selected_page_surface_with_redaction(
        self: _TextEditingHost,
    ) -> tuple[int, PageSurfaceLabel] | None:
        """Return the visible page surface that owns a redaction selection."""
        for label_index, candidate_label in enumerate(self._page_labels):
            if not isinstance(candidate_label, PageSurfaceLabel):
                continue
            if not candidate_label.selected_redaction_rectangles():
                continue
            return self._visible_page_indexes[label_index], candidate_label

        return None
