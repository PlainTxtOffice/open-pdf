"""Contracts and construction for persisted OCR results."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from src.adapters.ocr.cache import OcrCache

if TYPE_CHECKING:
    from pathlib import Path

    from src.domains.document.models import PdfOcrPageResult


class OcrResultStore(Protocol):
    """Describe persistence required by the desktop OCR workflow."""

    def load_results(self, source_path: Path) -> tuple[PdfOcrPageResult, ...]:
        """Return persisted OCR results for one document."""
        ...

    def save_result(
        self,
        source_path: Path,
        result: PdfOcrPageResult,
    ) -> None:
        """Persist one OCR page result for a document."""
        ...

    def save_results(
        self,
        source_path: Path,
        results: tuple[PdfOcrPageResult, ...],
    ) -> None:
        """Persist all OCR results for one document."""
        ...


def local_ocr_result_store(cache_dir: Path) -> OcrResultStore:
    """Build the local OCR result-store implementation."""
    return OcrCache(cache_dir=cache_dir)
