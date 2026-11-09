"""Domain models for PDF navigation, search results, and OCR state."""

from __future__ import annotations

from dataclasses import dataclass

type Rectangle = tuple[float, float, float, float]


type PdfPageWord = tuple[float, float, float, float, str, int, int, int]


@dataclass(slots=True, frozen=True)
class PdfSearchMatch:
    """Summarizes search matches for one page."""

    page_index: int
    rectangles: tuple[Rectangle, ...]


@dataclass(slots=True, frozen=True)
class PdfOcrPageResult:
    """Stores derived OCR text and geometry for one page."""

    page_index: int
    text: str
    words: tuple[PdfPageWord, ...]
    engine_name: str
    language_codes: tuple[str, ...] = ()
    confidence: float | None = None


@dataclass(slots=True, frozen=True)
class PdfTextSpan:
    """One run of text sharing a font, size, and colour on a page.

    - `bounds` is `(x0, y0, x1, y1)` in PDF user space.
    - `span_index` identifies the span within its page, so a caller can
      name a span again after re-extracting.
    - `origin` is the text baseline start, which replacement draws from.
    """

    page_index: int
    span_index: int
    text: str
    bounds: tuple[float, float, float, float]
    origin: tuple[float, float]
    font_name: str
    font_size: float
    color: int


@dataclass(slots=True, frozen=True)
class PdfOutlineItem:
    """Represents one PDF outline entry."""

    toc_index: int
    level: int
    title: str
    page_index: int


@dataclass(slots=True, frozen=True)
class PdfPageLink:
    """Represents one clickable PDF link hotspot on a rendered page."""

    bounds: tuple[float, float, float, float]
    target_page_index: int | None = None
    target_point: tuple[float, float] | None = None
    target_zoom: float | None = None
    target_fit: str | None = None
    named_destination: str | None = None
    uri: str | None = None
    file_path: str | None = None


@dataclass(slots=True, frozen=True)
class PdfMetadata:
    """Represents editable PDF metadata fields used by the UI."""

    info_dict: dict[str, str]
    custom_info_dict: dict[str, str]
    xmp_xml: str

    @property
    def title(self) -> str:
        """Return the normalized document title from the Info dictionary."""
        return self.info_dict.get("title", "")

    @property
    def author(self) -> str:
        """Return the normalized document author from the Info dictionary."""
        return self.info_dict.get("author", "")
