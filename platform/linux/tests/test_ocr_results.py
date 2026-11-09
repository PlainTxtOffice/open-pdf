"""Tests for the OCR result collaborator."""

import pytest
from open_pdf.application.document.text.ocr import recognize_page

from open_pdf.domains.document.models import PdfOcrPageResult
from open_pdf.domains.document.pages.text.ocr import OcrResults


def _result(page_index: int) -> PdfOcrPageResult:
    return PdfOcrPageResult(
        page_index=page_index,
        text="hello",
        words=(),
        engine_name="test",
    )


def test_store_rejects_out_of_range_page():
    ocr = OcrResults()
    with pytest.raises(ValueError, match="out of range"):
        ocr.store(_result(5), page_count=2)


def test_all_returns_results_ordered_by_page():
    ocr = OcrResults()
    ocr.store(_result(2), page_count=3)
    ocr.store(_result(0), page_count=3)
    assert [result.page_index for result in ocr.all()] == [0, 2]


def test_clear_drops_every_result():
    ocr = OcrResults()
    ocr.store(_result(0), page_count=1)
    ocr.clear()
    assert not ocr.has_any()


def test_run_without_backend_raises():
    ocr = OcrResults()
    with pytest.raises(RuntimeError, match="not configured"):
        recognize_page(None, ocr, document=None, page_index=0)


def test_wrong_page_backend_result_is_not_stored():
    from types import SimpleNamespace

    class Backend:
        def recognize_page(self, document, page_index, *, language_codes):
            return _result(page_index + 1)

    ocr = OcrResults()
    with pytest.raises(RuntimeError, match="wrong page"):
        recognize_page(Backend(), ocr, SimpleNamespace(page_count=3), 0)
    assert not ocr.has_any()
