"""Load, render, save, and extract OCR-fallback text for a PDF document."""

from __future__ import annotations

from typing import TYPE_CHECKING

from open_pdf.adapters.document.file_identity import references_same_file
from open_pdf.adapters.document.pymupdf.content.editing import (
    delete_document_page,
    insert_blank_document_page,
    move_document_page,
    redact_page_rectangles,
    replace_text_span,
    rotate_page_clockwise,
)
from open_pdf.adapters.document.pymupdf.content.metadata import (
    read_document_metadata,
    write_document_metadata,
)
from open_pdf.adapters.document.pymupdf.content.outline import (
    append_outline_item,
    delete_outline_item,
    outline_items,
    rename_outline_item,
)
from open_pdf.adapters.document.pymupdf.content.text import (
    extract_page_text,
    extract_page_words,
    page_text_spans,
)
from open_pdf.adapters.document.pymupdf.lifecycle import (
    can_save_incrementally,
    close_document,
    load_document_page,
    open_document,
    save_document,
    save_document_copy,
    save_document_in_place,
)
from open_pdf.adapters.document.pymupdf.links import (
    page_link_target_position,
    page_links,
    pdf_point_for_display_position,
    resolve_page_link_target,
)
from open_pdf.adapters.document.pymupdf.rendering import (
    page_display_size,
    page_size_points,
    render_page,
    render_thumbnail,
)
from open_pdf.application.document.notes import DocumentNotes
from open_pdf.application.document.redaction import redact_rectangles
from open_pdf.application.document.text.ocr import recognize_page
from open_pdf.application.document.text.search import search_document
from open_pdf.domains.document.models import (
    PdfMetadata,
    PdfOcrPageResult,
    PdfPageLink,
    PdfPageWord,
    PdfSearchMatch,
    PdfTextSpan,
)
from open_pdf.domains.document.pages.history import PageHistory, ScrollState
from open_pdf.domains.document.pages.reordering import (
    blank_page_position,
    dirty_pages_after_delete,
    dirty_pages_after_insert,
    dirty_pages_after_move,
    page_index_after_delete,
    page_index_after_move,
    validate_page_index,
)
from open_pdf.domains.document.pages.text.ocr import OcrResults
from open_pdf.domains.document.pages.text.spans import (
    span_for_rectangles,
)
from open_pdf.domains.document.pages.view_state import PdfViewState
from open_pdf.domains.document.properties.metadata import normalize_metadata
from open_pdf.domains.document.properties.outlines import (
    validate_bookmark_title,
    validate_outline_index,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    import pymupdf

    from open_pdf.adapters.ocr.backend import PdfOcrBackend
    from open_pdf.domains.document.models import PdfOutlineItem


# US Letter in points, used only when a document has no page to copy.
_DEFAULT_PAGE_SIZE_POINTS = (612.0, 792.0)


class PdfDocument:
    """Wraps the active PDF and its current view/edit state."""

    def __init__(self, *, ocr_backend: PdfOcrBackend | None = None) -> None:
        """Initialize with no open document."""
        self._document: pymupdf.Document | None = None
        self._source_path: Path | None = None
        self._password: str | None = None
        self._ocr = OcrResults()
        self._ocr_backend = ocr_backend
        self._history = PageHistory()
        self._is_dirty = False
        self._dirty_page_indexes: set[int] = set()
        self._render_revision = 0
        self._notes = DocumentNotes()
        self.state = PdfViewState()

    @property
    def source_path(self) -> Path | None:
        """Return the path of the currently open PDF, if any.

        Returns:
            The active document path, or None when no document is loaded.

        """
        return self._source_path

    @property
    def render_revision(self) -> int:
        """Return the revision used to invalidate cached render handles."""
        return self._render_revision

    def has_document(self) -> bool:
        """Return whether a PDF is open and has at least one page.

        Returns:
            True when a document is loaded and has pages.

        """
        return self._document is not None and self.state.has_pages()

    def open_document(self, path: Path) -> None:
        """Open a PDF and reset navigation state.

        - Closes any previously open document before loading `path`.
        - Resets page selection, zoom state, and navigation history.
        """
        self.open_document_with_password(path, password=None)

    def open_document_with_password(
        self,
        path: Path,
        *,
        password: str | None,
    ) -> None:
        """Open a PDF using an optional password and reset navigation state."""
        self.close_document()
        self._document = open_document(path, password=password)
        self._source_path = path
        self._password = password
        self._ocr.clear()
        self._is_dirty = False
        self._dirty_page_indexes.clear()
        self._notes.load(self._document)
        self._bump_render_revision()
        self.state.reset(page_count=self._document.page_count)
        if self.state.has_pages():
            self._push_current_page_history()

    def close_document(self) -> None:
        """Close the active PDF and clear all view state."""
        close_document(self._document)

        self._document = None
        self._source_path = None
        self._password = None
        self._ocr.clear()
        self._history.reset()
        self._is_dirty = False
        self._dirty_page_indexes.clear()
        self._notes = DocumentNotes()
        self._bump_render_revision()
        self.state.reset(page_count=0)

    def go_to_page(
        self,
        page_index: int,
        *,
        record_history: bool = True,
    ) -> None:
        """Show a specific page in the active document.

        - Clamps `page_index` through the shared view state rules.
        - Records the jump in history unless `record_history` is false.
        """
        self.state.set_page(page_index)
        if record_history and self.state.has_pages():
            self._push_current_page_history()

    def next_page(self) -> None:
        """Advance to the next page."""
        self.state.next_page()
        if self.state.has_pages():
            self._push_current_page_history()

    def previous_page(self) -> None:
        """Return to the previous page."""
        self.state.previous_page()
        if self.state.has_pages():
            self._push_current_page_history()

    def can_go_back_history(self) -> bool:
        """Return whether a back-history entry is available."""
        return self._history.can_go_back()

    def can_go_forward_history(self) -> bool:
        """Return whether a forward-history entry is available."""
        return self._history.can_go_forward()

    def _push_current_page_history(self) -> None:
        """Record the current page as a history entry without a position."""
        self._history.push(
            ScrollState(page_index=self.state.current_page_index),
        )

    def record_history_position(
        self,
        *,
        x_pdf: float | None,
        y_pdf: float | None,
    ) -> None:
        """Attach the reader's live scroll position to the current entry.

        - Call this before navigating away so that coming back returns to
          where the reader actually was, not to the top of the page.
        """
        if not self.state.has_pages():
            return

        self._history.rewrite_current(
            ScrollState(
                page_index=self.state.current_page_index,
                x_pdf=x_pdf,
                y_pdf=y_pdf,
            ),
        )

    def go_back_history(self) -> ScrollState | None:
        """Move to the previous history entry and return its position.

        Returns:
            The restored scroll state, or None when none is available.

        """
        target = self._history.go_back()
        if target is None:
            return None

        self.go_to_page(target.page_index, record_history=False)
        return target

    def go_forward_history(self) -> ScrollState | None:
        """Move to the next history entry and return its position.

        Returns:
            The restored scroll state, or None when none is available.

        """
        target = self._history.go_forward()
        if target is None:
            return None

        self.go_to_page(target.page_index, record_history=False)
        return target

    def zoom_in(self) -> None:
        """Increase the current zoom level."""
        self.state.zoom_in()

    def zoom_out(self) -> None:
        """Decrease the current zoom level."""
        self.state.zoom_out()

    def rotate_clockwise(self) -> None:
        """Rotate the current page 90 degrees clockwise."""
        page_index = self.state.current_page_index
        rotate_page_clockwise(self._require_document(), page_index)
        self._ocr.clear()
        self._is_dirty = True
        self._dirty_page_indexes.add(page_index)
        self._bump_render_revision()

    def insert_blank_page(self, *, at_index: int) -> None:
        """Insert a blank page at `at_index` and make it the current page.

        - The new page copies the size of its neighbour, so it matches the
          document rather than defaulting to Letter.
        - `at_index` is clamped to the document, so the document end is a
          valid insertion point.
        """
        document = self._require_document()
        page_count = document.page_count
        insert_index, neighbour_index = blank_page_position(
            at_index,
            page_count=page_count,
        )
        size = (
            page_size_points(document, neighbour_index)
            if page_count > 0
            else _DEFAULT_PAGE_SIZE_POINTS
        )

        insert_blank_document_page(
            document,
            page_index=insert_index,
            size=size,
        )

        self._ocr.clear()
        self._is_dirty = True
        self._dirty_page_indexes = dirty_pages_after_insert(
            self._dirty_page_indexes,
            inserted_index=insert_index,
            page_count=document.page_count,
        )
        self._bump_render_revision()
        self.state.page_count = document.page_count
        self.state.set_page(insert_index)
        self._history.reset()
        self._push_current_page_history()

    def delete_page(self, page_index: int) -> None:
        """Delete one page and reindex the remaining document state.

        Raises:
            ValueError: If the page index is out of range.

        """
        document = self._require_document()
        page_index = validate_page_index(
            page_index,
            page_count=document.page_count,
        )

        current_page_index = self.state.current_page_index
        delete_document_page(document, page_index)

        remaining_page_count = document.page_count
        self._ocr.clear()
        self._is_dirty = True
        self._dirty_page_indexes = dirty_pages_after_delete(
            self._dirty_page_indexes,
            deleted_index=page_index,
            remaining_page_count=remaining_page_count,
        )
        self._bump_render_revision()

        if remaining_page_count <= 0:
            self._history.reset()
            self.state.reset(page_count=0)
            return

        updated_page_index = page_index_after_delete(
            current_page_index,
            deleted_index=page_index,
            remaining_page_count=remaining_page_count,
        )

        self.state.page_count = remaining_page_count
        self.state.set_page(updated_page_index)
        self._history.reset()
        self._push_current_page_history()

    def move_page(self, page_index: int, destination_index: int) -> None:
        """Move one page and reindex the affected document state.

        Raises:
            ValueError: If either page index is out of range.

        """
        document = self._require_document()
        page_count = document.page_count
        page_index = validate_page_index(page_index, page_count=page_count)
        destination_index = validate_page_index(
            destination_index,
            page_count=page_count,
        )
        if page_index == destination_index:
            return

        current_page_index = self.state.current_page_index
        move_document_page(document, page_index, destination_index)

        self._ocr.clear()
        self._is_dirty = True
        self._dirty_page_indexes = dirty_pages_after_move(
            self._dirty_page_indexes,
            page_index=page_index,
            destination_index=destination_index,
        )
        self._bump_render_revision()

        self.state.page_count = page_count
        self.state.set_page(
            page_index_after_move(
                current_page_index,
                page_index=page_index,
                destination_index=destination_index,
            ),
        )
        self._history.reset()
        self._push_current_page_history()

    def redact_text_rectangles(
        self,
        *,
        page_index: int,
        rectangles: Sequence[tuple[float, float, float, float]],
    ) -> bool:
        """Redact content inside one page's rectangles.

        Returns:
            True when at least one non-empty rectangle was applied.

        Raises:
            ValueError: If the page index is out of range.

        """
        if not redact_rectangles(
            self._require_document(),
            page_index,
            rectangles,
            apply_redactions=redact_page_rectangles,
        ):
            return False

        self._ocr.clear()
        self._is_dirty = True
        self._dirty_page_indexes.add(page_index)
        self._bump_render_revision()
        return True

    def is_dirty(self) -> bool:
        """Return whether the document has unsaved edits."""
        return self._is_dirty

    def notes_text(self) -> str:
        """Return the plain-text notes embedded in the active PDF."""
        self._require_document()
        return self._notes.text()

    def update_notes(self, text: str) -> bool:
        """Replace the embedded plain-text notes when their text changed."""
        self._require_document()
        if self.notes_text() == text:
            return False

        self._notes.update(text)
        self._is_dirty = True
        return True

    def has_ocr_backend(self) -> bool:
        """Return whether an OCR backend is configured."""
        return self._ocr_backend is not None

    def has_ocr_result(self, page_index: int | None = None) -> bool:
        """Return whether OCR output exists for the requested page."""
        return self._ocr.has_result(self._resolve_page_index(page_index))

    def has_ocr_results(self) -> bool:
        """Return whether any OCR output is stored for the active document."""
        return self._ocr.has_any()

    def ocr_result(
        self,
        page_index: int | None = None,
    ) -> PdfOcrPageResult | None:
        """Return the stored OCR output for the requested page, if present."""
        return self._ocr.result(self._resolve_page_index(page_index))

    def run_ocr(
        self,
        page_index: int | None = None,
        *,
        language_codes: tuple[str, ...] = (),
    ) -> PdfOcrPageResult:
        """Run OCR for one page and store the derived text result."""
        return recognize_page(
            self._ocr_backend,
            self._ocr,
            self._require_document(),
            self._resolve_page_index(page_index),
            language_codes=language_codes,
        )

    def store_ocr_result(self, result: PdfOcrPageResult) -> None:
        """Store one derived OCR page result for the active document."""
        self._ocr.store(
            result,
            page_count=self._require_document().page_count,
        )

    def replace_ocr_results(
        self,
        results: Sequence[PdfOcrPageResult],
    ) -> None:
        """Replace all stored OCR output for the active document."""
        self._ocr.replace(
            results,
            page_count=self._require_document().page_count,
        )

    def ocr_results(self) -> tuple[PdfOcrPageResult, ...]:
        """Return all stored OCR results ordered by page index."""
        return self._ocr.all()

    def is_page_dirty(self, page_index: int) -> bool:
        """Return whether a page has unsaved in-memory edits."""
        return page_index in self._dirty_page_indexes

    def can_save(self) -> bool:
        """Return whether a save would write meaningful changes.

        Returns:
            True when a document is open, has a source path, and has unsaved
            edits.

        """
        document = self._document
        return (
            document is not None
            and self._source_path is not None
            and self._is_dirty
        )

    def save(self) -> None:
        """Write the current document state back to the opened file.

        Raises:
            RuntimeError: If no file-backed document is open.

        """
        document = self._require_document()
        source_path = self._source_path
        if source_path is None:
            msg = "No opened file is available to save."
            raise RuntimeError(msg)

        current_page_index = self.state.current_page_index
        current_zoom = self.state.zoom
        self._notes.flush(document)

        if can_save_incrementally(document):
            save_document(document)
        else:
            try:
                save_document_in_place(document, source_path)
                replacement_document = open_document(
                    source_path,
                    password=self._password,
                )
            except Exception:
                if document.is_closed:
                    self._document = open_document(
                        source_path,
                        password=self._password,
                    )
                    self._restore_view_after_reload(
                        page_index=current_page_index,
                        zoom=current_zoom,
                    )
                raise

            self._document = replacement_document
            self._restore_view_after_reload(
                page_index=current_page_index,
                zoom=current_zoom,
            )

        self._is_dirty = False
        self._dirty_page_indexes.clear()
        self._notes.mark_saved()
        self._bump_render_revision()

    def save_as(self, path: Path) -> None:
        """Write the current document state to `path` and adopt it as source."""
        document = self._require_document()
        source_path = self._source_path
        if source_path is not None and references_same_file(path, source_path):
            self.save()
            return

        current_page_index = self.state.current_page_index
        current_zoom = self.state.zoom
        self._notes.flush(document)

        save_document_copy(document, path)

        replacement_document = open_document(path, password=self._password)
        close_document(document)
        self._document = replacement_document
        self._source_path = path
        self._is_dirty = False
        self._dirty_page_indexes.clear()
        self._notes.mark_saved()
        self._restore_view_after_reload(
            page_index=current_page_index,
            zoom=current_zoom,
        )
        self._bump_render_revision()

    def render_page(
        self,
        page_index: int,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> pymupdf.Pixmap:
        """Render a page from the active in-memory document."""
        document = self._require_document()
        return render_page(
            document,
            page_index,
            zoom=self.state.zoom,
            device_pixel_ratio=device_pixel_ratio,
        )

    def render_page_at_zoom(
        self,
        page_index: int,
        *,
        zoom: float,
        device_pixel_ratio: float = 1.0,
    ) -> pymupdf.Pixmap:
        """Render a page from the active in-memory document at `zoom`."""
        document = self._require_document()
        return render_page(
            document,
            page_index,
            zoom=zoom,
            device_pixel_ratio=device_pixel_ratio,
        )

    def render_thumbnail(
        self,
        page_index: int,
        *,
        max_dimension: int = 160,
    ) -> pymupdf.Pixmap:
        """Render a thumbnail from the active in-memory document."""
        document = self._require_document()
        return render_thumbnail(
            document,
            page_index,
            max_dimension=max_dimension,
        )

    def page_display_size(self, page_index: int) -> tuple[int, int]:
        """Return the rendered page size for the current zoom level.

        Returns:
            The page width and height in pixels for the current zoom level.

        """
        document = self._require_document()
        return page_display_size(
            document,
            page_index,
            zoom=self.state.zoom,
        )

    def page_size_points(self, page_index: int) -> tuple[float, float]:
        """Return one page's unscaled size in PDF points.

        Returns:
            The page width and height in points, independent of the current
            zoom level.

        """
        document = self._require_document()
        return page_size_points(document, page_index)

    def page_text(self, page_index: int | None = None) -> str:
        """Return extracted text for a page.

        Returns:
            The extracted plain text for the requested page. Uses the current
            page when `page_index` is omitted.

        """
        index = self._resolve_page_index(page_index)
        page_text, _ = self._page_text_and_words(index)
        return page_text

    def page_words(
        self,
        page_index: int | None = None,
    ) -> list[PdfPageWord]:
        """Return extracted word boxes for a page."""
        index = self._resolve_page_index(page_index)
        _, page_words = self._page_text_and_words(index)
        return page_words

    def page_links(
        self,
        page_index: int | None = None,
    ) -> list[PdfPageLink]:
        """Return clickable links for a page in the current render space."""
        index = self._resolve_page_index(page_index)
        return page_links(
            self._require_document(),
            index,
            zoom=self.state.zoom,
        )

    def text_spans(self, *, page_index: int) -> list[PdfTextSpan]:
        """Return the styled text spans on one page."""
        document = self._require_document()
        return page_text_spans(
            load_document_page(document, page_index), page_index
        )

    def span_for_rectangles(
        self,
        *,
        page_index: int,
        rectangles: Sequence[tuple[float, float, float, float]],
    ) -> PdfTextSpan | None:
        """Return the text span a page selection covers, if any."""
        return span_for_rectangles(
            self.text_spans(page_index=page_index),
            rectangles,
        )

    def replace_text_span(
        self,
        *,
        span: PdfTextSpan,
        text: str,
    ) -> bool:
        """Replace one text span's contents and report whether it changed.

        Returns:
            True when the span text differed and the page was rewritten.

        """
        if text == span.text:
            return False

        changed = replace_text_span(
            self._require_document(),
            span=span,
            text=text,
        )
        if not changed:
            return False

        self._ocr.clear()
        self._is_dirty = True
        self._dirty_page_indexes.add(span.page_index)
        self._bump_render_revision()
        return True

    def pdf_point_for_display_position(
        self,
        *,
        page_index: int,
        position: tuple[float, float],
    ) -> tuple[float, float] | None:
        """Resolve a display-space position back into PDF-space units."""
        return pdf_point_for_display_position(
            self._require_document(),
            page_index=page_index,
            position=position,
            zoom=self.state.zoom,
        )

    def page_link_target_position(
        self,
        *,
        target_page_index: int | None,
        target_point: tuple[float, float] | None,
    ) -> tuple[float, float] | None:
        """Resolve a raw PDF link destination into current display space."""
        return page_link_target_position(
            self._require_document(),
            target_page_index=target_page_index,
            target_point=target_point,
            zoom=self.state.zoom,
        )

    def resolve_page_link_target(
        self,
        *,
        target_page_index: int | None,
        target_point: tuple[float, float] | None,
        named_destination: str | None,
    ) -> tuple[int, tuple[float, float] | None] | None:
        """Resolve a PDF link into a destination page and display position."""
        return resolve_page_link_target(
            self._require_document(),
            target_page_index=target_page_index,
            target_point=target_point,
            named_destination=named_destination,
            zoom=self.state.zoom,
        )

    def search(self, query: str) -> list[PdfSearchMatch]:
        """Return search matches across the active document.

        Returns:
            The matches for `query`, or an empty list when `query` is blank.

        """
        if not query.strip():
            return []

        return search_document(self._require_document(), self._ocr, query)

    def add_bookmark(
        self,
        title: str,
        *,
        page_index: int | None = None,
    ) -> None:
        """Append one top-level bookmark to the current document.

        Raises:
            ValueError: If the title is empty or the page index is out of range.

        """
        bookmark_title = validate_bookmark_title(title)

        target_page_index = self._resolve_page_index(page_index)
        validate_page_index(target_page_index, page_count=self.state.page_count)

        append_outline_item(
            self._require_document(),
            title=bookmark_title,
            page_index=target_page_index,
        )
        self._is_dirty = True

    def rename_bookmark(self, toc_index: int, title: str) -> None:
        """Rename one outline entry in the current document.

        Raises:
            ValueError: If the title is empty or the TOC index is out of range.

        """
        bookmark_title = validate_bookmark_title(title)

        outline_entry_count = len(self.outline_items())
        validate_outline_index(toc_index, entry_count=outline_entry_count)

        rename_outline_item(
            self._require_document(),
            toc_index=toc_index,
            title=bookmark_title,
        )
        self._is_dirty = True

    def delete_bookmark(self, toc_index: int) -> None:
        """Delete one outline entry and any nested child bookmarks.

        Raises:
            ValueError: If the TOC index is out of range.

        """
        outline_entry_count = len(self.outline_items())
        validate_outline_index(toc_index, entry_count=outline_entry_count)

        delete_outline_item(
            self._require_document(),
            toc_index=toc_index,
        )
        self._is_dirty = True

    def outline_items(self) -> list[PdfOutlineItem]:
        """Return the normalized outline entries for the active document.

        Returns:
            The outline items with zero-based page indexes.

        """
        return outline_items(self._require_document())

    def metadata(self) -> PdfMetadata:
        """Return the editable metadata fields for the active document."""
        info_dict, custom_info_dict, xmp_xml = read_document_metadata(
            self._require_document(),
        )
        return PdfMetadata(
            info_dict=info_dict,
            custom_info_dict=custom_info_dict,
            xmp_xml=xmp_xml,
        )

    def update_metadata(
        self,
        *,
        info_dict: Mapping[str, str],
        custom_info_dict: Mapping[str, str] | None = None,
        xmp_xml: str,
    ) -> None:
        """Update the editable metadata fields for the active document."""
        current_metadata = self.metadata()
        normalized = normalize_metadata(
            current_metadata,
            info_dict=info_dict,
            custom_info_dict=custom_info_dict,
            xmp_xml=xmp_xml,
        )
        if current_metadata == normalized:
            return

        write_document_metadata(
            self._require_document(),
            info_dict=normalized.info_dict,
            custom_info_dict=normalized.custom_info_dict,
            xmp_xml=normalized.xmp_xml,
        )
        self._is_dirty = True

    def current_page(self) -> pymupdf.Page:
        """Return the currently selected page object.

        Returns:
            The active PyMuPDF page for the current page index.

        """
        document = self._require_document()
        return load_document_page(document, self.state.current_page_index)

    def _page_text_and_words(
        self,
        page_index: int,
    ) -> tuple[str, list[PdfPageWord]]:
        """Return native text first and fall back to OCR when needed."""
        page = load_document_page(self._require_document(), page_index)
        native_words = extract_page_words(page)
        if native_words:
            return extract_page_text(page).strip(), native_words

        ocr_result = self._ocr.result(page_index)
        if ocr_result is None:
            return "", []

        return ocr_result.text.strip(), list(ocr_result.words)

    def _restore_view_after_reload(
        self,
        *,
        page_index: int,
        zoom: float,
    ) -> None:
        """Re-apply page selection and zoom after swapping the document."""
        document = self._require_document()
        self.state.page_count = document.page_count
        self.state.set_page(page_index)
        self.state.set_zoom(zoom)
        self._history.reset()
        if self.state.has_pages():
            self._push_current_page_history()

    def _require_document(self) -> pymupdf.Document:
        """Return the active document or raise when none is open.

        Returns:
            The currently open PDF document.

        Raises:
            RuntimeError: No PDF document is loaded.

        """
        if self._document is None:
            msg = "No PDF document is loaded."
            raise RuntimeError(msg)

        return self._document

    def _resolve_page_index(self, page_index: int | None) -> int:
        """Return the requested page index, defaulting to the current page."""
        if page_index is None:
            return self.state.current_page_index

        return page_index

    def _bump_render_revision(self) -> None:
        """Advance the render revision after any document-source change."""
        self._render_revision += 1
