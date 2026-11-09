"""Optional Tesseract-backed OCR adapter."""

from __future__ import annotations

import importlib
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import pymupdf

from open_pdf.domains.document.models import PdfOcrPageResult, PdfPageWord

if TYPE_CHECKING:
    from open_pdf.adapters.ocr.backend import PdfOcrBackend


class _PytesseractNamespace(Protocol):
    """Describe the mutable nested pytesseract namespace."""

    tesseract_cmd: str


class _PytesseractOutput(Protocol):
    """Describe the pytesseract output constants used by the adapter."""

    DICT: object


class _PytesseractModule(Protocol):
    """Describe the minimal pytesseract API required by the adapter."""

    pytesseract: _PytesseractNamespace
    Output: _PytesseractOutput

    def image_to_data(
        self,
        image: object,
        *,
        lang: str | None,
        output_type: object,
    ) -> dict[str, list[object]]: ...


class _ImageModule(Protocol):
    """Describe the minimal PIL.Image module API used by the adapter."""

    def frombytes(
        self,
        mode: str,
        size: tuple[int, int],
        samples: bytes,
    ) -> object: ...


_DEFAULT_TESSERACT_RENDER_ZOOM = 2.0
_TESSERACT_COMMAND_ENV_VAR = "TESSERACT_CMD"


class TesseractOcrBackend:
    """Recognize page text using Tesseract through pytesseract."""

    def __init__(
        self,
        *,
        pytesseract_module: _PytesseractModule,
        image_module: _ImageModule,
        executable_path: Path,
        render_zoom: float = _DEFAULT_TESSERACT_RENDER_ZOOM,
    ) -> None:
        """Store the Python wrapper, image module, and executable path."""
        self._pytesseract = pytesseract_module
        self._image_module = image_module
        self._executable_path = executable_path
        self._render_zoom = render_zoom

    def recognize_page(
        self,
        document: pymupdf.Document,
        page_index: int,
        *,
        language_codes: tuple[str, ...],
    ) -> PdfOcrPageResult:
        """Return OCR text and word boxes for one page."""
        page = document.load_page(page_index)
        pixmap = self._render_page_for_ocr(page)
        image = self._image_from_pixmap(pixmap)

        self._pytesseract.pytesseract.tesseract_cmd = str(
            self._executable_path,
        )
        ocr_data = self._pytesseract.image_to_data(
            image,
            lang=_language_argument(language_codes),
            output_type=self._pytesseract.Output.DICT,
        )

        words, confidence = self._words_from_ocr_data(ocr_data)
        return PdfOcrPageResult(
            page_index=page_index,
            text=_text_from_words(words),
            words=tuple(words),
            engine_name="tesseract",
            language_codes=language_codes,
            confidence=confidence,
        )

    def _render_page_for_ocr(self, page: pymupdf.Page) -> pymupdf.Pixmap:
        matrix = pymupdf.Matrix(self._render_zoom, self._render_zoom)
        return page.get_pixmap(matrix=matrix, alpha=False)

    def _image_from_pixmap(self, pixmap: pymupdf.Pixmap) -> object:
        image_mode = "L" if pixmap.n == 1 else "RGB"
        return self._image_module.frombytes(
            image_mode,
            (int(pixmap.w), int(pixmap.h)),
            pixmap.samples,
        )

    def _words_from_ocr_data(
        self,
        ocr_data: dict[str, list[object]],
    ) -> tuple[list[PdfPageWord], float | None]:
        raw_texts = ocr_data.get("text", [])
        words: list[PdfPageWord] = []
        confidence_values: list[float] = []
        for word_index, raw_text in enumerate(raw_texts):
            if not isinstance(raw_text, str):
                continue

            word_text = raw_text.strip()
            if not word_text:
                continue

            confidence = _confidence_at(ocr_data, word_index)
            if confidence is not None and confidence >= 0:
                confidence_values.append(confidence)

            left = _float_at(ocr_data, "left", word_index) / self._render_zoom
            top = _float_at(ocr_data, "top", word_index) / self._render_zoom
            width = _float_at(ocr_data, "width", word_index) / self._render_zoom
            height = (
                _float_at(ocr_data, "height", word_index) / self._render_zoom
            )
            words.append(
                (
                    left,
                    top,
                    left + max(width, 1.0),
                    top + max(height, 1.0),
                    word_text,
                    _int_at(ocr_data, "block_num", word_index),
                    _int_at(ocr_data, "line_num", word_index),
                    _int_at(ocr_data, "word_num", word_index),
                ),
            )

        average_confidence = None
        if confidence_values:
            average_confidence = sum(confidence_values) / len(confidence_values)

        return words, average_confidence


def create_tesseract_ocr_backend() -> PdfOcrBackend | None:
    """Return a Tesseract OCR backend when both wrapper and executable exist."""
    modules = _load_tesseract_modules()
    if modules is None:
        return None

    executable_path = _find_tesseract_executable()
    if executable_path is None:
        return None

    pytesseract_module, image_module = modules
    return TesseractOcrBackend(
        pytesseract_module=pytesseract_module,
        image_module=image_module,
        executable_path=executable_path,
    )


def tesseract_setup_message() -> str | None:
    """Return a user-facing setup message when Tesseract OCR is unavailable."""
    modules = _load_tesseract_modules()
    executable_path = _find_tesseract_executable()
    if modules is not None and executable_path is not None:
        return None

    missing_steps: list[str] = []
    if modules is None:
        missing_steps.append(
            "Install the optional Python OCR dependencies with "
            '"pip install -e .[ocr]".',
        )
    if executable_path is None:
        missing_steps.append(
            "Install Tesseract OCR and add tesseract.exe to PATH, or set "
            "TESSERACT_CMD to its full path.",
        )

    return (
        "OCR is unavailable because Tesseract is not fully configured.\n\n"
        + "\n".join(f"- {step}" for step in missing_steps)
    )


def _load_tesseract_modules() -> tuple[_PytesseractModule, _ImageModule] | None:
    try:
        pytesseract_module = cast(
            "_PytesseractModule",
            importlib.import_module("pytesseract"),
        )
        image_module = cast(
            "_ImageModule",
            importlib.import_module("PIL.Image"),
        )
    except ImportError:
        return None

    return pytesseract_module, image_module


def _find_tesseract_executable() -> Path | None:
    configured_path = os.environ.get(_TESSERACT_COMMAND_ENV_VAR)
    if configured_path:
        candidate_path = Path(configured_path).expanduser()
        if candidate_path.exists():
            return candidate_path

    command_path = shutil.which("tesseract")
    if command_path is None:
        return None

    return Path(command_path)


def _language_argument(language_codes: tuple[str, ...]) -> str | None:
    if not language_codes:
        return None

    return "+".join(language_codes)


def _text_from_words(words: list[PdfPageWord]) -> str:
    if not words:
        return ""

    parts: list[str] = []
    previous_key: tuple[int, int] | None = None
    for word in words:
        current_key = (word[5], word[6])
        if previous_key is not None:
            parts.append("\n" if current_key != previous_key else " ")
        parts.append(word[4])
        previous_key = current_key

    return "".join(parts)


def _float_at(
    ocr_data: dict[str, list[object]],
    key: str,
    index: int,
) -> float:
    values = ocr_data.get(key, [])
    if index >= len(values):
        return 0.0

    raw_value = values[index]
    if isinstance(raw_value, int | float):
        return float(raw_value)
    if isinstance(raw_value, str):
        try:
            return float(raw_value)
        except ValueError:
            return 0.0
    return 0.0


def _int_at(
    ocr_data: dict[str, list[object]],
    key: str,
    index: int,
) -> int:
    values = ocr_data.get(key, [])
    if index >= len(values):
        return 0

    raw_value = values[index]
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, float):
        return int(raw_value)
    if isinstance(raw_value, str):
        try:
            return int(raw_value)
        except ValueError:
            return 0
    return 0


def _confidence_at(
    ocr_data: dict[str, list[object]],
    index: int,
) -> float | None:
    values = ocr_data.get("conf", [])
    if index >= len(values):
        return None

    raw_value = values[index]
    if isinstance(raw_value, int | float):
        return float(raw_value)
    if isinstance(raw_value, str):
        try:
            return float(raw_value)
        except ValueError:
            return None
    return None
