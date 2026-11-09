"""Local JSON cache for derived OCR results."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from open_pdf.domains.document.models import PdfOcrPageResult, PdfPageWord

if TYPE_CHECKING:
    from pathlib import Path


_MINIMUM_PAGE_WORD_FIELDS = 8


class OcrCache:
    """Persist derived OCR output under the local data directory."""

    def __init__(self, *, cache_dir: Path) -> None:
        """Store the directory used for OCR cache files."""
        self._cache_dir = cache_dir

    def load_results(self, source_path: Path) -> tuple[PdfOcrPageResult, ...]:
        """Return cached OCR results when the on-disk fingerprint matches."""
        cache_path = self._cache_path_for(source_path)
        record = self._read_record(cache_path)
        if record is None:
            return ()

        fingerprint = self._fingerprint_for(source_path)
        if record.get("fingerprint") != fingerprint:
            return ()

        raw_pages = record.get("pages")
        if not isinstance(raw_pages, dict):
            return ()

        results: list[PdfOcrPageResult] = []
        for raw_page_index, raw_result in raw_pages.items():
            if not isinstance(raw_page_index, str):
                continue
            if not isinstance(raw_result, dict):
                continue

            try:
                page_index = int(raw_page_index)
            except ValueError:
                continue

            results.append(
                PdfOcrPageResult(
                    page_index=page_index,
                    text=_coerce_text(raw_result.get("text")),
                    words=_deserialize_words(raw_result.get("words")),
                    engine_name=_coerce_text(raw_result.get("engine_name")),
                    language_codes=_deserialize_language_codes(
                        raw_result.get("language_codes"),
                    ),
                    confidence=_deserialize_confidence(
                        raw_result.get("confidence"),
                    ),
                ),
            )

        return tuple(sorted(results, key=lambda result: result.page_index))

    def save_result(self, source_path: Path, result: PdfOcrPageResult) -> None:
        """Persist one OCR page result for the supplied document path."""
        cache_path = self._cache_path_for(source_path)
        record = self._read_record(cache_path) or {}
        fingerprint = self._fingerprint_for(source_path)
        if record.get("fingerprint") != fingerprint:
            record = {
                "fingerprint": fingerprint,
                "pages": {},
            }

        raw_pages = record.get("pages")
        if not isinstance(raw_pages, dict):
            raw_pages = {}
            record["pages"] = raw_pages

        raw_pages[str(result.page_index)] = {
            "text": result.text,
            "words": [list(word) for word in result.words],
            "engine_name": result.engine_name,
            "language_codes": list(result.language_codes),
            "confidence": result.confidence,
        }
        self._write_record(cache_path, record)

    def save_results(
        self,
        source_path: Path,
        results: tuple[PdfOcrPageResult, ...],
    ) -> None:
        """Persist all OCR results for one document path."""
        cache_path = self._cache_path_for(source_path)
        record = {
            "fingerprint": self._fingerprint_for(source_path),
            "pages": {
                str(result.page_index): {
                    "text": result.text,
                    "words": [list(word) for word in result.words],
                    "engine_name": result.engine_name,
                    "language_codes": list(result.language_codes),
                    "confidence": result.confidence,
                }
                for result in results
            },
        }
        self._write_record(cache_path, record)

    def _cache_path_for(self, source_path: Path) -> Path:
        normalized_path = str(source_path.expanduser().resolve(strict=False))
        filename = hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()
        return self._cache_dir / f"{filename}.json"

    @staticmethod
    def _fingerprint_for(source_path: Path) -> dict[str, int | str]:
        stats = source_path.stat()
        return {
            "path": str(source_path.expanduser().resolve(strict=False)),
            "size": int(stats.st_size),
            "mtime_ns": int(stats.st_mtime_ns),
        }

    @staticmethod
    def _read_record(cache_path: Path) -> dict[str, object] | None:
        try:
            raw_text = cache_path.read_text(encoding="utf-8")
        except OSError:
            return None

        try:
            raw_record = json.loads(raw_text)
        except json.JSONDecodeError:
            return None

        if not isinstance(raw_record, dict):
            return None

        return raw_record

    def _write_record(
        self,
        cache_path: Path,
        record: dict[str, object],
    ) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(record, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )


def _coerce_text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _deserialize_words(raw_words: object) -> tuple[PdfPageWord, ...]:
    if not isinstance(raw_words, list):
        return ()

    deserialized_words: list[PdfPageWord] = []
    for raw_word in raw_words:
        if (
            not isinstance(raw_word, list | tuple)
            or len(raw_word) < _MINIMUM_PAGE_WORD_FIELDS
        ):
            continue

        text = raw_word[4]
        if not isinstance(text, str) or not text:
            continue

        deserialized_words.append(
            (
                float(raw_word[0]),
                float(raw_word[1]),
                float(raw_word[2]),
                float(raw_word[3]),
                text,
                int(raw_word[5]),
                int(raw_word[6]),
                int(raw_word[7]),
            ),
        )

    return tuple(deserialized_words)


def _deserialize_language_codes(raw_value: object) -> tuple[str, ...]:
    if not isinstance(raw_value, list):
        return ()

    return tuple(value for value in raw_value if isinstance(value, str))


def _deserialize_confidence(raw_value: object) -> float | None:
    if isinstance(raw_value, int | float):
        return float(raw_value)

    return None
