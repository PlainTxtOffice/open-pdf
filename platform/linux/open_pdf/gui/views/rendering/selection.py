"""Coordinate page selection modes, overlays, and context menus."""

from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import QPoint, Qt

from open_pdf.adapters.document.errors import PDF_IO_ERRORS
from open_pdf.gui.views.rendering.page_surface import PageSurfaceLabel

if TYPE_CHECKING:
    from PySide6.QtWidgets import (
        QLabel,
        QMenu,
        QStatusBar,
        QTextEdit,
        QToolButton,
        QWidget,
    )

    from open_pdf.application.document.session import PdfDocument
    from open_pdf.domains.document.models import (
        PdfPageLink,
    )


logger = logging.getLogger(__name__)


class _PageSelectionHost(Protocol):
    """Describe the window operations required by this workflow."""

    _document: PdfDocument

    _page_text: QTextEdit

    _page_labels: list[QLabel]

    _visible_page_indexes: list[int]

    _is_text_selection_mode: bool

    _is_pdf_edit_mode: bool

    _mouse_mode_indicator: QToolButton

    _rendered_page_indexes: set[int]

    _words_loaded_pages: set[int]

    _active_page_surface_context_menu: QMenu | None

    def _handle_page_link_activated(self, link: PdfPageLink) -> None: ...

    def _persist_pane_visibility_settings(self) -> None: ...

    def statusBar(self) -> QStatusBar: ...  # noqa: N802

    def _label_index_for_page(
        self,
        page_index: int | None,
    ) -> int | None: ...

    def _add_bookmark_from_selected_text(
        self,
        title: str | None = None,
        *,
        page_index: int | None = None,
    ) -> None: ...

    def _apply_context_menu_theme(
        self,
        menu: QMenu,
        *,
        source_widget: QWidget,
    ) -> None: ...

    def _apply_text_selection_mode(self) -> None: ...

    def _bookmark_title_from_text(
        self,
        selected_text: str,
    ) -> str | None: ...

    def _ensure_page_words_loaded(
        self,
        page_index: int,
    ) -> None: ...

    def _remove_selected_text(
        self,
        *,
        page_index: int | None = None,
        page_label: PageSurfaceLabel | None = None,
    ) -> None: ...

    def _replace_selected_text(
        self,
        *,
        page_index: int | None = None,
        page_label: PageSurfaceLabel | None = None,
    ) -> None: ...

    def _set_browse_mouse_mode(self) -> None: ...

    def _show_page_surface_context_menu(
        self,
        *,
        page_index: int,
        page_label: PageSurfaceLabel,
        position: QPoint,
    ) -> None: ...

    def _update_mouse_mode_indicator(self) -> None: ...


class PageSelectionMixin:
    """Coordinate page selection and interaction."""

    if TYPE_CHECKING:
        _active_page_surface_context_menu: QMenu | None

    def _set_browse_mouse_mode(self: _PageSelectionHost) -> None:
        self._is_pdf_edit_mode = False
        self._is_text_selection_mode = True
        self._apply_text_selection_mode()
        self._persist_pane_visibility_settings()

    def _set_text_selection_mouse_mode(self: _PageSelectionHost) -> None:
        self._is_pdf_edit_mode = False
        self._is_text_selection_mode = True
        self._apply_text_selection_mode()
        self._persist_pane_visibility_settings()

    def _enter_pdf_edit_mode(self: _PageSelectionHost) -> None:
        """Enter the text-selection mode used for content edits."""
        if not self._document.has_document():
            return

        self._is_pdf_edit_mode = True
        self._is_text_selection_mode = False
        self._apply_text_selection_mode()
        self.statusBar().showMessage(
            "Edit PDF mode: drag over text, then choose Replace Text "
            "or Remove Content.",
            5000,
        )

    def _toggle_mouse_mode(self: _PageSelectionHost) -> None:
        self._set_browse_mouse_mode()

    def _apply_text_selection_mode(self: _PageSelectionHost) -> None:
        if self._is_text_selection_mode:
            interaction_flags = (
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
        else:
            interaction_flags = Qt.TextInteractionFlag.NoTextInteraction
            text_cursor = self._page_text.textCursor()
            text_cursor.clearSelection()
            self._page_text.setTextCursor(text_cursor)

        self._page_text.setTextInteractionFlags(interaction_flags)
        for label_index, page_label in enumerate(self._page_labels):
            if not isinstance(page_label, PageSurfaceLabel):
                continue
            page_index = self._visible_page_indexes[label_index]
            page_label.set_text_selection_enabled(enabled=False)
            page_label.set_edit_selection_enabled(enabled=False)
            if self._is_pdf_edit_mode:
                page_label.set_edit_selection_enabled(enabled=True)
                continue

            page_label.set_text_selection_enabled(
                enabled=self._is_text_selection_mode,
            )
            if (
                self._is_text_selection_mode
                and page_index in self._rendered_page_indexes
            ):
                self._ensure_page_words_loaded(page_index)

        self._update_mouse_mode_indicator()

    def _update_mouse_mode_indicator(self: _PageSelectionHost) -> None:
        mode_name = "Edit PDF" if self._is_pdf_edit_mode else "Read"
        self._mouse_mode_indicator.setText(f"Mode: {mode_name}")

    def _show_page_text_context_menu(
        self: _PageSelectionHost,
        position: QPoint,
    ) -> None:
        menu = self._page_text.createStandardContextMenu()
        self._apply_context_menu_theme(menu, source_widget=self._page_text)
        bookmark_title = self._bookmark_title_from_text(
            self._page_text.textCursor().selectedText(),
        )
        bookmark_action = None
        if bookmark_title is not None:
            menu.addSeparator()
            bookmark_action = menu.addAction("Add Bookmark From Selection")

        selected_action = menu.exec(
            self._page_text.viewport().mapToGlobal(position),
        )
        if selected_action is bookmark_action and bookmark_title is not None:
            self._add_bookmark_from_selected_text(bookmark_title)

    def _configure_page_surface(
        self: _PageSelectionHost,
        page_label: PageSurfaceLabel,
        page_index: int,
    ) -> None:
        # Word boxes are loaded lazily (see _ensure_page_words_loaded) when
        # the page enters the render window, so opening/zooming a large PDF
        # does not extract text for every page up front.
        page_label.set_text_selection_enabled(
            enabled=self._is_text_selection_mode,
        )
        page_label.link_activated.connect(self._handle_page_link_activated)
        page_label.text_layer().customContextMenuRequested.connect(
            lambda position, current_page_index=page_index, current_label=page_label: (  # noqa: E501
                self._show_page_surface_context_menu(
                    page_index=current_page_index,
                    page_label=current_label,
                    position=position,
                )
            ),
        )

    def _ensure_page_words_loaded(
        self: _PageSelectionHost,
        page_index: int,
    ) -> None:
        """Load text-overlay word boxes for one page on first need.

        - No-op outside text-selection mode or if already loaded for the
          current label generation (the set is cleared when labels rebuild,
          so a zoom change reloads at the new scale).
        """
        if not self._is_text_selection_mode:
            return
        if page_index in self._words_loaded_pages:
            return
        label_index = self._label_index_for_page(page_index)
        if label_index is None:
            return

        page_label = self._page_labels[label_index]
        if not isinstance(page_label, PageSurfaceLabel):
            return

        try:
            page_text_words = self._document.page_words(page_index)
        except PDF_IO_ERRORS:
            logger.exception(
                "Failed to load text overlay for page %d",
                page_index + 1,
            )
            # Mark handled so a deterministic extraction failure does not
            # re-raise on every re-render/scroll. The set is cleared when
            # labels rebuild (zoom/rotate/open), which retries then.
            self._words_loaded_pages.add(page_index)
            return

        page_label.set_page_text_words(
            page_text_words,
            zoom=self._document.state.zoom,
        )
        self._words_loaded_pages.add(page_index)

    def _show_page_surface_context_menu(
        self: _PageSelectionHost,
        *,
        page_index: int,
        page_label: PageSurfaceLabel,
        position: QPoint,
    ) -> None:
        text_layer = page_label.text_layer()
        selected_text = page_label.selected_text()
        selected_rectangles = page_label.selected_redaction_rectangles()
        menu = text_layer.createStandardContextMenu()
        self._apply_context_menu_theme(menu, source_widget=text_layer)

        bookmark_title = self._bookmark_title_from_text(selected_text)
        if bookmark_title is not None:
            menu.addSeparator()
            bookmark_action = menu.addAction("Add Bookmark From Selection")
            bookmark_action.triggered.connect(
                partial(
                    self._add_bookmark_from_selected_text,
                    bookmark_title,
                    page_index=page_index,
                ),
            )

        if selected_rectangles:
            if bookmark_title is None:
                menu.addSeparator()
            replace_text_action = menu.addAction("Replace Text...")
            replace_text_action.triggered.connect(
                partial(
                    self._replace_selected_text,
                    page_index=page_index,
                    page_label=page_label,
                ),
            )
            remove_text_action = menu.addAction("Remove Content")
            remove_text_action.triggered.connect(
                partial(
                    self._remove_selected_text,
                    page_index=page_index,
                    page_label=page_label,
                ),
            )

        menu.aboutToHide.connect(menu.deleteLater)
        self._active_page_surface_context_menu = menu
        menu.aboutToHide.connect(
            lambda: setattr(
                self,
                "_active_page_surface_context_menu",
                None,
            ),
        )
        menu.popup(text_layer.viewport().mapToGlobal(position))
