from pathlib import Path

import pymupdf
import pytest

from src.domains.document.errors import (
    IncorrectPasswordError,
    PasswordRequiredError,
)
from src.domains.document.models import PdfOcrPageResult
from src.domains.document.reader import PdfDocument


def create_sample_pdf(path: Path) -> None:
    document = pymupdf.open()

    page_one = document.new_page()
    page_one.insert_text((72, 72), "alpha beta gamma")

    page_two = document.new_page()
    page_two.insert_text((72, 72), "delta beta epsilon")

    document.save(path)
    document.close()


def info_dictionary_xref(document: pymupdf.Document) -> int:
    value_type, value = document.xref_get_key(-1, "Info")
    assert value_type == "xref"
    return int(value.split()[0])


def add_custom_info_property(
    path: Path,
    *,
    name: str,
    value: str,
) -> None:
    document = pymupdf.open(path)
    try:
        document.set_metadata({"title": "Metadata sample"})
        info_xref = info_dictionary_xref(document)
        document.xref_set_key(
            info_xref,
            name,
            pymupdf.get_pdf_str(value),
        )
        document.saveIncr()
    finally:
        document.close()


def create_three_page_pdf(path: Path) -> None:
    document = pymupdf.open()
    try:
        for page_number in range(1, 4):
            page = document.new_page()
            page.insert_text((72, 72), f"page {page_number}")

        document.save(path)
    finally:
        document.close()


def create_sized_pdf(path: Path, *, width: float, height: float) -> None:
    document = pymupdf.open()
    try:
        page = document.new_page(width=width, height=height)
        page.insert_text((20, 40), "sized page")
        document.save(path)
    finally:
        document.close()


def create_image_only_pdf(path: Path, *, page_count: int = 1) -> None:
    document = pymupdf.open()
    try:
        for _ in range(page_count):
            document.new_page()
        document.save(path)
    finally:
        document.close()


def create_native_and_blank_pdf(path: Path) -> None:
    document = pymupdf.open()
    try:
        page_one = document.new_page()
        page_one.insert_text((72, 72), "native needle")
        document.new_page()
        document.save(path)
    finally:
        document.close()


def create_password_protected_pdf(path: Path) -> None:
    document = pymupdf.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), "locked")
        document.save(
            path,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner-pass",
            user_pw="user-pass",
        )
    finally:
        document.close()


def create_linked_pdf(path: Path) -> None:
    document = pymupdf.open()
    try:
        document.new_page()
        document.new_page()

        page_one = document.load_page(0)
        page_two = document.load_page(1)
        page_two.insert_text((72, 72), "target page")

        page_one.insert_text((72, 72), "external link")
        page_one.insert_link(
            {
                "kind": pymupdf.LINK_URI,
                "from": pymupdf.Rect(72, 72, 152, 96),
                "uri": "https://example.com/spec",
            },
        )
        page_one.insert_text((72, 140), "internal link")
        page_one.insert_link(
            {
                "kind": pymupdf.LINK_GOTO,
                "from": pymupdf.Rect(72, 140, 152, 164),
                "page": 1,
                "to": pymupdf.Point(20, 250),
            },
        )

        document.save(path)
    finally:
        document.close()


def build_ocr_page_result(page_index: int, text: str) -> PdfOcrPageResult:
    words = []
    cursor_x = 72.0
    for word_index, word in enumerate(text.split()):
        word_width = max(len(word) * 8.0, 12.0)
        words.append(
            (
                cursor_x,
                72.0,
                cursor_x + word_width,
                92.0,
                word,
                0,
                0,
                word_index,
            ),
        )
        cursor_x += word_width + 8.0

    return PdfOcrPageResult(
        page_index=page_index,
        text=text,
        words=tuple(words),
        engine_name="fake-ocr",
    )


class _FakeOcrBackend:
    def __init__(self, results_by_page: dict[int, PdfOcrPageResult]) -> None:
        self._results_by_page = results_by_page
        self.calls: list[tuple[int, tuple[str, ...]]] = []

    def recognize_page(
        self,
        document: pymupdf.Document,
        page_index: int,
        *,
        language_codes: tuple[str, ...],
    ) -> PdfOcrPageResult:
        del document
        self.calls.append((page_index, language_codes))
        return self._results_by_page[page_index]


def test_navigation_history_tracks_direct_page_jumps(tmp_path: Path) -> None:
    pdf_path = tmp_path / "history.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    service.go_to_page(1)
    service.go_to_page(0)

    service.go_back_history()
    assert service.state.current_page_index == 1

    service.go_back_history()
    assert service.state.current_page_index == 0

    service.go_forward_history()
    assert service.state.current_page_index == 1


def test_search_returns_matching_pages_and_text(tmp_path: Path) -> None:
    pdf_path = tmp_path / "search.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    matches = service.search("beta")

    assert [match.page_index for match in matches] == [0, 1]
    assert all(match.rectangles for match in matches)
    assert "alpha beta gamma" in service.page_text(0)


def test_search_blank_query_returns_no_matches_without_document() -> None:
    service = PdfDocument()

    assert service.search("   ") == []


def test_redact_text_rectangles_removes_selected_words_from_page(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "redact-selected-text.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    first_word_rect = service.page_words(0)[0][:4]

    changed = service.redact_text_rectangles(
        page_index=0,
        rectangles=[first_word_rect],
    )

    assert changed is True
    assert "alpha" not in service.page_text(0)
    assert "beta" in service.page_text(0)
    assert service.is_dirty() is True
    assert service.is_page_dirty(0) is True
    assert service.can_save() is True


def test_save_writes_redaction_back_to_opened_file(tmp_path: Path) -> None:
    pdf_path = tmp_path / "save-redaction.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    first_word_rect = service.page_words(0)[0][:4]
    service.redact_text_rectangles(
        page_index=0,
        rectangles=[first_word_rect],
    )

    assert service.can_save() is True

    service.save()

    assert service.can_save() is False

    service.close_document()

    document = pymupdf.open(pdf_path)
    try:
        page_text = document.load_page(0).get_text("text")
        assert isinstance(page_text, str)
        assert "alpha" not in page_text
        assert "beta" in page_text
    finally:
        document.close()


def test_run_ocr_uses_fallback_text_and_words_without_marking_dirty(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "image-only.pdf"
    create_image_only_pdf(pdf_path)

    backend = _FakeOcrBackend(
        {0: build_ocr_page_result(0, "scanned alpha beta")},
    )
    service = PdfDocument(ocr_backend=backend)
    service.open_document(pdf_path)

    assert service.page_text(0) == ""
    assert service.page_words(0) == []

    service.run_ocr(0)

    assert service.page_text(0) == "scanned alpha beta"
    assert [word[4] for word in service.page_words(0)] == [
        "scanned",
        "alpha",
        "beta",
    ]
    assert service.is_dirty() is False
    assert backend.calls == [(0, ())]


def test_native_text_takes_precedence_over_ocr_result(tmp_path: Path) -> None:
    pdf_path = tmp_path / "native-precedence.pdf"
    create_sample_pdf(pdf_path)

    backend = _FakeOcrBackend(
        {0: build_ocr_page_result(0, "ocr override text")},
    )
    service = PdfDocument(ocr_backend=backend)
    service.open_document(pdf_path)

    service.run_ocr(0)

    assert service.page_text(0) == "alpha beta gamma"
    assert [word[4] for word in service.page_words(0)] == [
        "alpha",
        "beta",
        "gamma",
    ]


def test_search_composes_native_and_ocr_page_matches(tmp_path: Path) -> None:
    pdf_path = tmp_path / "mixed-search.pdf"
    create_native_and_blank_pdf(pdf_path)

    backend = _FakeOcrBackend(
        {1: build_ocr_page_result(1, "scanned needle")},
    )
    service = PdfDocument(ocr_backend=backend)
    service.open_document(pdf_path)
    service.run_ocr(1)

    matches = service.search("needle")

    assert [match.page_index for match in matches] == [0, 1]
    assert all(match.rectangles for match in matches)


def test_render_page_scales_raster_for_device_pixel_ratio(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "hidpi.pdf"
    create_sized_pdf(pdf_path, width=200, height=100)

    service = PdfDocument()
    service.open_document(pdf_path)

    default_render = service.render_page(0)
    hidpi_render = service.render_page(0, device_pixel_ratio=1.5)

    assert service.page_display_size(0) == (200, 100)
    assert (default_render.width, default_render.height) == (200, 100)
    assert (hidpi_render.width, hidpi_render.height) == (300, 150)


def test_open_document_rejects_password_protected_pdf(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "protected.pdf"
    create_password_protected_pdf(pdf_path)

    service = PdfDocument()

    with pytest.raises(PasswordRequiredError):
        service.open_document(pdf_path)

    assert service.has_document() is False
    assert service.source_path is None


def test_open_document_accepts_password_for_protected_pdf(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "protected-accept.pdf"
    create_password_protected_pdf(pdf_path)

    service = PdfDocument()
    service.open_document_with_password(pdf_path, password="user-pass")

    assert service.has_document() is True
    assert service.source_path == pdf_path


def test_open_document_rejects_incorrect_password(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "protected-wrong.pdf"
    create_password_protected_pdf(pdf_path)

    service = PdfDocument()

    with pytest.raises(IncorrectPasswordError):
        service.open_document_with_password(pdf_path, password="wrong-pass")


def test_page_links_returns_external_and_internal_targets(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "links.pdf"
    create_linked_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    links = service.page_links(0)

    assert [link.uri for link in links] == [
        "https://example.com/spec",
        None,
    ]
    assert [link.target_page_index for link in links] == [None, 1]
    assert [link.target_point for link in links] == [None, (20.0, 250.0)]
    assert links[0].bounds == (72.0, 72.0, 152.0, 96.0)
    assert links[1].bounds == (72.0, 140.0, 152.0, 164.0)


def test_page_link_target_position_resolves_pdf_destination_at_current_zoom(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "links-position.pdf"
    create_linked_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    link = service.page_links(0)[1]

    assert service.page_link_target_position(
        target_page_index=link.target_page_index,
        target_point=link.target_point,
    ) == (20.0, 592.0)


def test_page_links_preserve_xyz_destination_zoom(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "xyz-link.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    def _fake_get_links(page: pymupdf.Page) -> list[dict[str, object]]:
        if page.number == 0:
            return [
                {
                    "from": pymupdf.Rect(72, 72, 152, 96),
                    "kind": pymupdf.LINK_GOTO,
                    "page": 1,
                    "to": pymupdf.Point(20, 250),
                    "zoom": 2.25,
                },
            ]
        return []

    monkeypatch.setattr(pymupdf.Page, "get_links", _fake_get_links)

    link = service.page_links(0)[0]

    assert link.target_page_index == 1
    assert link.target_point == (20.0, 250.0)
    assert link.target_zoom == 2.25
    assert link.target_fit == "XYZ"


def test_page_links_preserve_named_destinations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "named-links.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    def _fake_get_links(page: pymupdf.Page) -> list[dict[str, object]]:
        if page.number == 0:
            return [
                {
                    "from": pymupdf.Rect(72, 72, 152, 96),
                    "nameddest": "chapter-2",
                },
            ]
        return []

    monkeypatch.setattr(pymupdf.Page, "get_links", _fake_get_links)

    links = service.page_links(0)

    assert len(links) == 1
    assert links[0].named_destination == "chapter-2"
    assert links[0].uri is None
    assert links[0].file_path is None
    assert links[0].target_page_index is None


def test_resolve_page_link_target_resolves_named_destinations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "named-target.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    def _fake_resolve_link(
        document: pymupdf.Document,
        uri: str | None = None,
        chapters: int = 0,
    ) -> tuple[int, float, float]:
        del document, chapters
        if uri == "#nameddest=chapter-2":
            return 1, 20.0, 250.0
        return -1, 0.0, 0.0

    monkeypatch.setattr(pymupdf.Document, "resolve_link", _fake_resolve_link)

    assert service.resolve_page_link_target(
        target_page_index=None,
        target_point=None,
        named_destination="chapter-2",
    ) == (1, (20.0, 592.0))


def test_outline_items_returns_pdf_bookmarks(tmp_path: Path) -> None:
    pdf_path = tmp_path / "outline.pdf"
    create_sample_pdf(pdf_path)

    document = pymupdf.open(pdf_path)
    document.set_toc([[1, "Intro", 1], [2, "Second page", 2]])
    document.saveIncr()
    document.close()

    service = PdfDocument()
    service.open_document(pdf_path)

    outline_items = service.outline_items()

    assert [item.title for item in outline_items] == ["Intro", "Second page"]
    assert [item.level for item in outline_items] == [1, 2]
    assert [item.page_index for item in outline_items] == [0, 1]


def test_save_writes_changes_back_to_opened_file(tmp_path: Path) -> None:
    pdf_path = tmp_path / "save.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    assert service.can_save() is False

    service.rotate_clockwise()

    assert service.can_save() is True

    service.save()

    assert service.can_save() is False

    service.close_document()

    document = pymupdf.open(pdf_path)
    try:
        assert document.load_page(0).rotation == 90
    finally:
        document.close()


def test_document_notes_are_embedded_and_persist_after_save(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "notes.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    assert service.notes_text() == ""
    assert service.update_notes("# Notes\n\nRemember this.") is True
    assert service.is_dirty() is True

    service.save()
    service.close_document()

    reopened_service = PdfDocument()
    reopened_service.open_document(pdf_path)

    assert reopened_service.notes_text() == "# Notes\n\nRemember this."
    assert reopened_service.is_dirty() is False

    document = pymupdf.open(pdf_path)
    try:
        assert "notes.txt" in document.embfile_names()
        assert "notes.md" not in document.embfile_names()
    finally:
        document.close()


def test_successive_note_edits_persist_complete_text(tmp_path: Path) -> None:
    pdf_path = tmp_path / "successive-notes.pdf"
    create_sample_pdf(pdf_path)
    service = PdfDocument()
    service.open_document(pdf_path)

    for partial_text in ("h", "he", "hel", "hell", "hello world"):
        assert service.update_notes(partial_text) is True

    service.save()
    service.close_document()

    reopened_service = PdfDocument()
    reopened_service.open_document(pdf_path)

    assert reopened_service.notes_text() == "hello world"


def test_clearing_document_notes_removes_embedded_attachment(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "cleared-notes.pdf"
    create_sample_pdf(pdf_path)
    service = PdfDocument()
    service.open_document(pdf_path)
    service.update_notes("temporary")
    service.save()

    assert service.update_notes("") is True
    service.save()
    service.close_document()

    document = pymupdf.open(pdf_path)
    try:
        assert "notes.txt" not in document.embfile_names()
        assert "notes.md" not in document.embfile_names()
    finally:
        document.close()


def test_legacy_markdown_notes_migrate_to_plain_text_on_save(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "legacy-notes.pdf"
    create_sample_pdf(pdf_path)
    document = pymupdf.open(pdf_path)
    document.embfile_add("notes.md", b"legacy note")
    document.saveIncr()
    document.close()

    service = PdfDocument()
    service.open_document(pdf_path)

    assert service.notes_text() == "legacy note"

    service.update_notes("legacy note updated")
    service.save()
    service.close_document()

    migrated_document = pymupdf.open(pdf_path)
    try:
        assert migrated_document.embfile_get("notes.txt") == (
            b"legacy note updated"
        )
        assert "notes.md" not in migrated_document.embfile_names()
    finally:
        migrated_document.close()


def test_save_as_rebinds_future_saves_to_target_file(tmp_path: Path) -> None:
    source_path = tmp_path / "source.pdf"
    target_path = tmp_path / "target.pdf"
    create_sample_pdf(source_path)

    service = PdfDocument()
    service.open_document(source_path)
    service.rotate_clockwise()

    service.save_as(target_path)

    assert service.source_path == target_path

    service.go_to_page(1)
    service.rotate_clockwise()

    assert service.can_save() is True

    service.save()
    service.close_document()

    source_document = pymupdf.open(source_path)
    try:
        assert source_document.load_page(0).rotation == 0
        assert source_document.load_page(1).rotation == 0
    finally:
        source_document.close()

    target_document = pymupdf.open(target_path)
    try:
        assert target_document.load_page(0).rotation == 90
        assert target_document.load_page(1).rotation == 90
    finally:
        target_document.close()


def test_save_as_preserves_password_protection(tmp_path: Path) -> None:
    source_path = tmp_path / "protected-source.pdf"
    target_path = tmp_path / "protected-target.pdf"
    create_password_protected_pdf(source_path)

    service = PdfDocument()
    service.open_document_with_password(source_path, password="user-pass")

    service.save_as(target_path)
    service.close_document()

    copied_document = pymupdf.open(target_path)
    try:
        assert copied_document.needs_pass
        assert copied_document.authenticate("user-pass") > 0
    finally:
        copied_document.close()


def test_delete_page_marks_document_dirty_and_reindexes_pages(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "delete-page.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    service.go_to_page(1)

    service.delete_page(0)

    assert service.state.page_count == 1
    assert service.state.current_page_index == 0
    assert service.is_dirty() is True
    assert service.can_save() is True
    assert service.is_page_dirty(0) is True
    assert "delta beta epsilon" in service.page_text(0)


def test_move_page_marks_document_dirty_and_keeps_moved_page_selected(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "move-page.pdf"
    create_three_page_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    service.go_to_page(1)

    service.move_page(1, 2)

    assert service.state.page_count == 3
    assert service.state.current_page_index == 2
    assert service.is_dirty() is True
    assert service.can_save() is True
    assert service.is_page_dirty(1) is True
    assert service.is_page_dirty(2) is True
    assert "page 3" in service.page_text(1)
    assert "page 2" in service.page_text(2)


def test_add_bookmark_appends_outline_entry_to_current_page(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "bookmark.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    service.go_to_page(1)

    service.add_bookmark("selected text")

    outline_items = service.outline_items()

    assert len(outline_items) == 1
    assert outline_items[0].title == "selected text"
    assert outline_items[0].page_index == 1
    assert service.is_dirty() is True


def test_rename_bookmark_updates_outline_title(tmp_path: Path) -> None:
    pdf_path = tmp_path / "rename-bookmark.pdf"
    create_sample_pdf(pdf_path)

    document = pymupdf.open(pdf_path)
    document.set_toc([[1, "Original", 1], [1, "Keep", 2]])
    document.saveIncr()
    document.close()

    service = PdfDocument()
    service.open_document(pdf_path)

    service.rename_bookmark(0, "Renamed")

    outline_items = service.outline_items()

    assert [item.title for item in outline_items] == ["Renamed", "Keep"]
    assert service.is_dirty() is True


def test_delete_bookmark_removes_selected_outline_subtree(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "delete-bookmark.pdf"
    create_sample_pdf(pdf_path)

    document = pymupdf.open(pdf_path)
    document.set_toc(
        [
            [1, "Parent", 1],
            [2, "Child", 1],
            [1, "Keep", 2],
        ]
    )
    document.saveIncr()
    document.close()

    service = PdfDocument()
    service.open_document(pdf_path)

    service.delete_bookmark(0)

    outline_items = service.outline_items()

    assert [item.title for item in outline_items] == ["Keep"]
    assert [item.level for item in outline_items] == [1]
    assert service.is_dirty() is True


def test_update_metadata_changes_title_and_author(tmp_path: Path) -> None:
    pdf_path = tmp_path / "metadata.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    updated_info_dict = dict(service.metadata().info_dict)
    updated_info_dict["title"] = "Project Plan"
    updated_info_dict["author"] = "Alex Writer"

    service.update_metadata(
        info_dict=updated_info_dict,
        xmp_xml="",
    )

    metadata = service.metadata()

    assert metadata.title == "Project Plan"
    assert metadata.author == "Alex Writer"
    assert service.is_dirty() is True

    service.save()
    service.close_document()

    document = pymupdf.open(pdf_path)
    try:
        assert document.metadata["title"] == "Project Plan"
        assert document.metadata["author"] == "Alex Writer"
    finally:
        document.close()


def test_metadata_reads_and_preserves_custom_info_property(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "metadata-custom-existing.pdf"
    create_sample_pdf(pdf_path)
    add_custom_info_property(pdf_path, name="edition", value="2")

    service = PdfDocument()
    service.open_document(pdf_path)

    metadata = service.metadata()

    assert metadata.custom_info_dict == {"edition": "2"}

    updated_info_dict = dict(metadata.info_dict)
    updated_info_dict["title"] = "Changed title"
    service.update_metadata(info_dict=updated_info_dict, xmp_xml="")
    service.save()
    service.close_document()

    document = pymupdf.open(pdf_path)
    try:
        info_xref = info_dictionary_xref(document)
        assert document.xref_get_key(info_xref, "edition") == (
            "string",
            "2",
        )
    finally:
        document.close()


def test_update_metadata_adds_edits_and_deletes_custom_properties(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "metadata-custom-update.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    service.update_metadata(
        info_dict=dict(service.metadata().info_dict),
        custom_info_dict={"edition": "2", "print_edition": "Second"},
        xmp_xml="",
    )

    assert service.metadata().custom_info_dict == {
        "edition": "2",
        "print_edition": "Second",
    }

    service.update_metadata(
        info_dict=dict(service.metadata().info_dict),
        custom_info_dict={"edition": "3"},
        xmp_xml="",
    )
    service.save()
    service.close_document()

    document = pymupdf.open(pdf_path)
    try:
        info_xref = info_dictionary_xref(document)
        assert document.xref_get_key(info_xref, "edition") == (
            "string",
            "3",
        )
        assert document.xref_get_key(info_xref, "print_edition") == (
            "null",
            "null",
        )
    finally:
        document.close()


@pytest.mark.parametrize(
    ("field_name", "field_value", "message"),
    [
        ("creationDate", "bad-date", "creationDate must use PDF date syntax"),
        (
            "modDate",
            "D:20240101120000+0500",
            "modDate must use PDF date syntax",
        ),
        ("trapped", "Maybe", "trapped must be True, False, or Unknown"),
    ],
)
def test_update_metadata_rejects_invalid_info_fields(
    field_name: str,
    field_value: str,
    message: str,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "metadata-invalid-info.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    updated_info_dict = dict(service.metadata().info_dict)
    updated_info_dict[field_name] = field_value

    with pytest.raises(ValueError, match=message):
        service.update_metadata(
            info_dict=updated_info_dict,
            xmp_xml="",
        )

    assert service.is_dirty() is False


def test_update_metadata_changes_xmp_xml(tmp_path: Path) -> None:
    pdf_path = tmp_path / "metadata-xmp.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    xmp_xml = (
        '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '    <rdf:Description rdf:about="" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        "      <dc:title>\n"
        "        <rdf:Alt>\n"
        '          <rdf:li xml:lang="x-default">Project Plan</rdf:li>\n'
        "        </rdf:Alt>\n"
        "      </dc:title>\n"
        "    </rdf:Description>\n"
        "  </rdf:RDF>\n"
        "</x:xmpmeta>\n"
        '<?xpacket end="w"?>'
    )

    service.update_metadata(
        info_dict=dict(service.metadata().info_dict),
        xmp_xml=xmp_xml,
    )

    metadata = service.metadata()

    assert metadata.xmp_xml == xmp_xml
    assert service.is_dirty() is True

    service.save()
    service.close_document()

    document = pymupdf.open(pdf_path)
    try:
        assert document.get_xml_metadata() == xmp_xml
    finally:
        document.close()


def test_save_as_onto_aliased_source_path_saves_in_place(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "alias-source.pdf"
    create_sample_pdf(pdf_path)
    (tmp_path / "sub").mkdir()
    aliased_path = tmp_path / "sub" / ".." / "alias-source.pdf"

    service = PdfDocument()
    service.open_document(pdf_path)
    service.rotate_clockwise()

    service.save_as(aliased_path)

    assert service.source_path == pdf_path
    assert service.is_dirty() is False

    service.close_document()

    document = pymupdf.open(pdf_path)
    try:
        assert document.page_count == 2
        assert document.load_page(0).rotation == 90
    finally:
        document.close()


def test_failed_full_rewrite_save_keeps_unsaved_edits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import src.domains.document.reader as reader_module

    pdf_path = tmp_path / "failed-save.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    service.rotate_clockwise()

    monkeypatch.setattr(
        reader_module,
        "can_save_incrementally",
        lambda _document: False,
    )

    def _failing_in_place_save(
        document: pymupdf.Document,
        path: Path,
    ) -> None:
        del document, path
        msg = "simulated write failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(
        reader_module,
        "save_document_in_place",
        _failing_in_place_save,
    )

    with pytest.raises(RuntimeError, match="simulated write failure"):
        service.save()

    assert service.is_dirty() is True
    assert service.can_save() is True
    assert service.current_page().rotation == 90


def test_failed_full_rewrite_save_reopens_when_document_was_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import src.domains.document.reader as reader_module

    pdf_path = tmp_path / "failed-save-closed.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    service.rotate_clockwise()

    monkeypatch.setattr(
        reader_module,
        "can_save_incrementally",
        lambda _document: False,
    )

    def _failing_in_place_save(
        document: pymupdf.Document,
        path: Path,
    ) -> None:
        del path
        document.close()
        msg = "simulated failure after close"
        raise RuntimeError(msg)

    monkeypatch.setattr(
        reader_module,
        "save_document_in_place",
        _failing_in_place_save,
    )

    with pytest.raises(RuntimeError, match="simulated failure after close"):
        service.save()

    assert service.has_document() is True
    assert service.page_text(0) != ""


def test_update_metadata_rejects_invalid_xmp_xml(tmp_path: Path) -> None:
    pdf_path = tmp_path / "metadata-invalid-xmp.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    with pytest.raises(ValueError, match="XMP metadata must be valid XML"):
        service.update_metadata(
            info_dict=dict(service.metadata().info_dict),
            xmp_xml="not xml",
        )

    assert service.is_dirty() is False


def test_history_restores_the_scroll_position_it_recorded(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "history-position.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    # The reader scrolled down page 0 before jumping to page 1.
    service.record_history_position(x_pdf=0.0, y_pdf=420.0)
    service.go_to_page(1)

    restored = service.go_back_history()

    assert restored is not None
    assert restored.page_index == 0
    assert restored.y_pdf == 420.0


def test_display_position_round_trips_back_to_its_pdf_point(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "round-trip.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    service.state.set_zoom(1.75)
    pdf_point = (120.0, 400.0)

    display = service.page_link_target_position(
        target_page_index=0,
        target_point=pdf_point,
    )
    assert display is not None
    restored = service.pdf_point_for_display_position(
        page_index=0,
        position=display,
    )

    assert restored is not None
    assert restored[0] == pytest.approx(pdf_point[0], abs=0.01)
    assert restored[1] == pytest.approx(pdf_point[1], abs=0.01)


def test_inserting_a_blank_page_shifts_the_following_pages(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "insert.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    service.insert_blank_page(at_index=1)

    assert service.state.page_count == 3
    assert "alpha beta gamma" in service.page_text(0)
    assert service.page_text(1).strip() == ""
    assert "delta beta epsilon" in service.page_text(2)


def test_inserted_page_matches_the_neighbour_page_size(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "insert-size.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)
    existing_size = service.page_size_points(0)

    service.insert_blank_page(at_index=1)

    assert service.page_size_points(1) == pytest.approx(existing_size)


def test_inserting_a_page_marks_the_document_dirty(tmp_path: Path) -> None:
    pdf_path = tmp_path / "insert-dirty.pdf"
    create_sample_pdf(pdf_path)

    service = PdfDocument()
    service.open_document(pdf_path)

    service.insert_blank_page(at_index=0)

    assert service.is_dirty() is True
    assert service.state.current_page_index == 0
