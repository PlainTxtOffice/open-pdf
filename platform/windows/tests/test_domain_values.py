"""Exercise pure rules without constructing an engine or GUI."""

import pytest

from open_pdf.domains.document.models import PdfMetadata
from open_pdf.domains.document.pages.reordering import (
    blank_page_position,
    page_index_after_delete,
)
from open_pdf.domains.document.pages.text.ocr_search import match_rectangles
from open_pdf.domains.document.properties.metadata import normalize_metadata
from open_pdf.domains.document.properties.notes import NotesState


def test_ocr_phrase_returns_plain_bounding_coordinates():
    words = [(1, 2, 3, 4, "Hello", 0, 0, 0), (5, 1, 9, 7, "WORLD", 0, 0, 1)]
    assert match_rectangles(words, " hello world ") == ((1, 1, 9, 7),)
    assert match_rectangles(words, "ell") == ((1, 2, 3, 4),)
    assert match_rectangles(words, " ") == ()


def test_metadata_omission_preserves_custom_properties_but_empty_clears():
    current = PdfMetadata({}, {"Owner": "Example"}, "")
    preserved = normalize_metadata(
        current, info_dict={"title": " Title "}, custom_info_dict=None, xmp_xml=" "
    )
    cleared = normalize_metadata(current, info_dict={}, custom_info_dict={}, xmp_xml="")
    assert preserved == PdfMetadata({"title": "Title"}, {"Owner": "Example"}, "")
    assert cleared.custom_info_dict == {}
    assert current.custom_info_dict == {"Owner": "Example"}


def test_notes_saved_state_tracks_reverting_an_edit():
    notes = NotesState()
    notes.load("stored")
    assert notes.is_saved()
    notes.update("edited")
    assert not notes.is_saved()
    notes.update("stored")
    assert notes.is_saved()
    notes.update("saved edit")
    notes.mark_saved()
    assert notes.is_saved()


@pytest.mark.parametrize("requested,count,expected", [(-3, 3, (0, 0)), (8, 3, (3, 2)), (0, 0, (0, -1))])
def test_blank_page_position_clamps_and_selects_neighbor(requested, count, expected):
    assert blank_page_position(requested, page_count=count) == expected


@pytest.mark.parametrize("current,deleted,count,expected", [(3, 1, 4, 2), (2, 2, 2, 1), (0, 2, 3, 0)])
def test_deletion_preserves_selected_page_when_possible(current, deleted, count, expected):
    assert page_index_after_delete(current, deleted_index=deleted, remaining_page_count=count) == expected
