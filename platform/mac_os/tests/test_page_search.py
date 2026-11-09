"""Tests for page search."""

from open_pdf.application.document.text.search import search_document


def test_blank_query_returns_no_matches():
    assert search_document(document=None, ocr=None, query="   ") == []
