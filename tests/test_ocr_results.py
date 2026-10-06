"""Tests for the OCR result collaborator."""

import pytest

from src.domains.document.models import PdfOcrPageResult
from src.domains.document.pages.text.ocr import OcrResults


def _result(page_index: int) -> PdfOcrPageResult:
    return PdfOcrPageResult(
        page_index=page_index,
        text="hello",
        words=(),
        engine_name="test",
    )


def test_store_rejects_out_of_range_page():
    ocr = OcrResults(backend=None)
    with pytest.raises(ValueError, match="out of range"):
        ocr.store(_result(5), page_count=2)


def test_all_returns_results_ordered_by_page():
    ocr = OcrResults(backend=None)
    ocr.store(_result(2), page_count=3)
    ocr.store(_result(0), page_count=3)
    assert [result.page_index for result in ocr.all()] == [0, 2]


def test_clear_drops_every_result():
    ocr = OcrResults(backend=None)
    ocr.store(_result(0), page_count=1)
    ocr.clear()
    assert not ocr.has_any()


def test_run_without_backend_raises():
    ocr = OcrResults(backend=None)
    with pytest.raises(RuntimeError, match="not configured"):
        ocr.run(document=None, page_index=0)
