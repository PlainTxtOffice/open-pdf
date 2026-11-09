from pathlib import Path
from types import SimpleNamespace

import pymupdf

from open_pdf.adapters.ocr.tesseract import (
    TesseractOcrBackend,
    create_tesseract_ocr_backend,
    tesseract_setup_message,
)


class _FakeImageModule:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[int, int], bytes]] = []

    def frombytes(
        self,
        mode: str,
        size: tuple[int, int],
        samples: bytes,
    ) -> object:
        self.calls.append((mode, size, samples))
        return object()


class _FakePyTesseractModule:
    def __init__(self, ocr_data: dict[str, list[object]]) -> None:
        self._ocr_data = ocr_data
        self.calls: list[tuple[object, str | None, object]] = []
        self.pytesseract = SimpleNamespace(tesseract_cmd="")
        self.Output = SimpleNamespace(DICT=object())

    def image_to_data(
        self,
        image: object,
        *,
        lang: str | None,
        output_type: object,
    ) -> dict[str, list[object]]:
        self.calls.append((image, lang, output_type))
        return self._ocr_data


def test_create_tesseract_ocr_backend_returns_none_when_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "open_pdf.adapters.ocr.tesseract._load_tesseract_modules",
        lambda: None,
    )

    assert create_tesseract_ocr_backend() is None


def test_create_tesseract_ocr_backend_returns_backend_when_available(
    monkeypatch,
    tmp_path: Path,
) -> None:
    fake_modules = (object(), object())
    executable_path = tmp_path / "tesseract.exe"
    executable_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "open_pdf.adapters.ocr.tesseract._load_tesseract_modules",
        lambda: fake_modules,
    )
    monkeypatch.setattr(
        "open_pdf.adapters.ocr.tesseract._find_tesseract_executable",
        lambda: executable_path,
    )

    backend = create_tesseract_ocr_backend()

    assert isinstance(backend, TesseractOcrBackend)


def test_tesseract_setup_message_lists_missing_dependencies_and_executable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "open_pdf.adapters.ocr.tesseract._load_tesseract_modules",
        lambda: None,
    )
    monkeypatch.setattr(
        "open_pdf.adapters.ocr.tesseract._find_tesseract_executable",
        lambda: None,
    )

    message = tesseract_setup_message()

    assert message is not None
    assert "pip install -e .[ocr]" in message
    assert "TESSERACT_CMD" in message
    assert "Tesseract" in message


def test_tesseract_backend_normalizes_boxes_and_text(tmp_path: Path) -> None:
    ocr_data = {
        "text": ["hello", "world", ""],
        "left": [20, 70, 0],
        "top": [30, 30, 0],
        "width": [40, 50, 0],
        "height": [10, 10, 0],
        "block_num": [1, 1, 0],
        "line_num": [1, 1, 0],
        "word_num": [1, 2, 0],
        "conf": [80, "70", -1],
    }
    pytesseract_module = _FakePyTesseractModule(ocr_data)
    image_module = _FakeImageModule()
    executable_path = tmp_path / "tesseract.exe"
    executable_path.write_text("", encoding="utf-8")
    backend = TesseractOcrBackend(
        pytesseract_module=pytesseract_module,
        image_module=image_module,
        executable_path=executable_path,
    )

    document = pymupdf.open()
    try:
        document.new_page(width=200, height=100)

        result = backend.recognize_page(document, 0, language_codes=("eng",))
    finally:
        document.close()

    assert pytesseract_module.pytesseract.tesseract_cmd == str(executable_path)
    assert pytesseract_module.calls and pytesseract_module.calls[0][1] == "eng"
    assert image_module.calls and image_module.calls[0][0] == "RGB"
    assert result.engine_name == "tesseract"
    assert result.text == "hello world"
    assert result.words == (
        (10.0, 15.0, 30.0, 20.0, "hello", 1, 1, 1),
        (35.0, 15.0, 60.0, 20.0, "world", 1, 1, 2),
    )
    assert result.confidence == 75.0
