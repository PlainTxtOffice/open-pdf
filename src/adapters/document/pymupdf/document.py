"""Adapters for PyMuPDF document persistence and rendering."""

from __future__ import annotations

import re
from contextlib import suppress
from typing import TYPE_CHECKING, Final
from uuid import uuid4

import pymupdf
from PySide6.QtCore import QXmlStreamReader

from src.domains.document.errors import (
    IncorrectPasswordError,
    PasswordRequiredError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

from src.domains.document.models import PdfPageLink, PdfTextSpan

_INFO_METADATA_KEYS = (
    "title",
    "author",
    "subject",
    "keywords",
    "creator",
    "producer",
    "creationDate",
    "modDate",
    "trapped",
    "format",
    "encryption",
)
_EDITABLE_INFO_METADATA_KEYS = tuple(
    key for key in _INFO_METADATA_KEYS if key not in {"format", "encryption"}
)
_STANDARD_INFO_PDF_KEYS = frozenset(
    {
        "Title",
        "Author",
        "Subject",
        "Keywords",
        "Creator",
        "Producer",
        "CreationDate",
        "ModDate",
        "Trapped",
    },
)
_CUSTOM_INFO_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_NAMED_DESTINATION_PREFIX = "#nameddest="
_PDF_ENCRYPT_KEEP: Final = int(getattr(pymupdf, "PDF_ENCRYPT_KEEP", 0))
_PDF_DATE_RE = re.compile(
    r"^D:"
    r"\d{4}"
    r"(\d{2}"
    r"(\d{2}"
    r"(\d{2}"
    r"(\d{2}"
    r"(\d{2}"
    r"((Z|[+-]\d{2}'\d{2}'))?"
    r")?)?)?)?)?$",
)
_TRAPPED_VALUES = frozenset({"", "True", "False", "Unknown"})
_XPACKET_PI_RE = re.compile(r"<\?xpacket\b[^?]*\?>", re.IGNORECASE)


def open_document(
    path: Path,
    *,
    password: str | None = None,
) -> pymupdf.Document:
    """Open a PDF document from disk."""
    document = pymupdf.open(path)
    if not document.needs_pass:
        return document

    attempted_password = "" if password is None else password
    if document.authenticate(attempted_password) > 0:
        return document

    document.close()
    if password is not None:
        msg = "The provided PDF password is incorrect."
        raise IncorrectPasswordError(msg)

    msg = "This PDF is password-protected and requires a password to open."
    raise PasswordRequiredError(msg)


def close_document(document: pymupdf.Document | None) -> None:
    """Close a document when one is open."""
    if document is not None:
        document.close()


def can_save_incrementally(document: pymupdf.Document) -> bool:
    """Return whether the document supports in-place incremental save."""
    return bool(document.can_save_incrementally())


def save_document(document: pymupdf.Document) -> None:
    """Write document changes back to the opened file."""
    document.saveIncr()


def save_document_copy(document: pymupdf.Document, path: Path) -> None:
    """Write document changes to a target path via an atomic replace."""
    temporary_path = _temporary_pdf_path(path)
    try:
        document.save(temporary_path, encryption=_PDF_ENCRYPT_KEEP)
        temporary_path.replace(path)
    except Exception:
        with suppress(OSError):
            temporary_path.unlink(missing_ok=True)
        raise


def save_document_in_place(document: pymupdf.Document, path: Path) -> None:
    """Write document changes back to the opened file via a safe replace."""
    temporary_path = _temporary_pdf_path(path)
    backup_path = _backup_pdf_path(path)
    source_backed_up = False
    try:
        document.save(temporary_path, encryption=_PDF_ENCRYPT_KEEP)
        document.close()
        path.replace(backup_path)
        source_backed_up = True
        temporary_path.replace(path)
    except Exception:
        with suppress(OSError):
            temporary_path.unlink(missing_ok=True)
        if source_backed_up and backup_path.exists() and not path.exists():
            backup_path.replace(path)
        raise
    else:
        backup_path.unlink(missing_ok=True)


def _temporary_pdf_path(path: Path) -> Path:
    while True:
        temporary_path = path.with_name(
            f".{path.stem}.{uuid4().hex}{path.suffix}.tmp",
        )
        if not temporary_path.exists():
            return temporary_path


def _backup_pdf_path(path: Path) -> Path:
    while True:
        backup_path = path.with_name(
            f".{path.stem}.{uuid4().hex}{path.suffix}.bak",
        )
        if not backup_path.exists():
            return backup_path


def insert_blank_document_page(
    document: pymupdf.Document,
    *,
    page_index: int,
    size: tuple[float, float],
) -> None:
    """Insert an empty page of `size` at `page_index`."""
    width, height = size
    document.new_page(pno=page_index, width=width, height=height)


def delete_document_page(
    document: pymupdf.Document,
    page_index: int,
) -> None:
    """Delete one page from the active document."""
    document.delete_page(page_index)


def move_document_page(
    document: pymupdf.Document,
    page_index: int,
    destination_index: int,
) -> None:
    """Move one page to another zero-based page position."""
    insert_index = destination_index
    if page_index < destination_index:
        insert_index = (
            -1
            if destination_index == document.page_count - 1
            else destination_index + 1
        )
    document.move_page(page_index, insert_index)


def redact_page_rectangles(
    document: pymupdf.Document,
    page_index: int,
    rectangles: Sequence[tuple[float, float, float, float]],
) -> bool:
    """Redact page content inside the supplied PDF-space rectangles."""
    page = document.load_page(page_index)
    added_redaction = False
    for x0, y0, x1, y1 in rectangles:
        rect = pymupdf.Rect(
            min(x0, x1),
            min(y0, y1),
            max(x0, x1),
            max(y0, y1),
        )
        if rect.is_empty:
            continue

        page.add_redact_annot(rect, fill=(1, 1, 1))
        added_redaction = True

    if not added_redaction:
        return False

    page.apply_redactions()
    return True


# Embedded subset fonts usually lack glyphs for characters the original
# text did not use, so replacement text falls back to a base-14 face.
_FALLBACK_FONT = "helv"
# Keep the replacement inside the span box rather than overflowing it.
_MIN_REPLACEMENT_FONT_SIZE = 4.0


def _replacement_font_name(font_name: str) -> str:
    """Return a font usable for arbitrary replacement characters."""
    base_14 = {"helv", "tiro", "cour", "times", "symb", "zadb"}
    normalized = font_name.rsplit("+", maxsplit=1)[-1].casefold()
    for candidate in base_14:
        if normalized.startswith(candidate):
            return candidate
    return _FALLBACK_FONT


def replace_text_span(
    document: pymupdf.Document,
    *,
    span: PdfTextSpan,
    text: str,
) -> bool:
    """Erase the text inside `bounds` and draw `text` on the same baseline.

    - Stays on one line: PDF has no reflow, so wrapping would collide with
      the line beneath. Longer text shrinks to fit the original width,
      down to a floor, and is allowed to run on if it still will not fit.

    Returns:
        True when the page was modified.

    """
    page = document.load_page(span.page_index)
    span_rect = pymupdf.Rect(*span.bounds)
    if span_rect.is_empty:
        return False

    page.add_redact_annot(span_rect)
    page.apply_redactions()

    if not text:
        return True

    replacement_font = _replacement_font_name(span.font_name)
    rgb = (
        ((span.color >> 16) & 0xFF) / 255.0,
        ((span.color >> 8) & 0xFF) / 255.0,
        (span.color & 0xFF) / 255.0,
    )
    available_width = span_rect.width
    size = span.font_size
    while size > _MIN_REPLACEMENT_FONT_SIZE:
        width = pymupdf.get_text_length(
            text,
            fontname=replacement_font,
            fontsize=size,
        )
        if width <= available_width:
            break
        size -= 0.5

    page.insert_text(
        pymupdf.Point(span.origin),
        text,
        fontname=replacement_font,
        fontsize=size,
        color=rgb,
    )
    return True


def _coerce_metadata_value(value: object) -> str:
    """Normalize an Info-dictionary value to a string."""
    return value if isinstance(value, str) else ""


def _info_dictionary_xref(document: pymupdf.Document) -> int | None:
    value_type, value = document.xref_get_key(-1, "Info")
    if value_type != "xref":
        return None
    return int(value.split()[0])


def _custom_string_info_keys(
    document: pymupdf.Document,
) -> tuple[int | None, dict[str, str]]:
    info_xref = _info_dictionary_xref(document)
    if info_xref is None:
        return None, {}

    decoded_to_pdf_key: dict[str, str] = {}
    for pdf_key in document.xref_get_keys(info_xref):
        if pdf_key in _STANDARD_INFO_PDF_KEYS:
            continue
        if _CUSTOM_INFO_NAME_RE.fullmatch(pdf_key) is None:
            continue
        value_type, _value = document.xref_get_key(info_xref, pdf_key)
        if value_type == "string":
            decoded_to_pdf_key[pdf_key] = pdf_key
    return info_xref, decoded_to_pdf_key


def _read_custom_info_metadata(
    document: pymupdf.Document,
) -> dict[str, str]:
    info_xref, custom_keys = _custom_string_info_keys(document)
    if info_xref is None:
        return {}
    return {
        name: document.xref_get_key(info_xref, pdf_key)[1]
        for name, pdf_key in sorted(custom_keys.items())
    }


def _write_custom_info_metadata(
    document: pymupdf.Document,
    custom_info_dict: Mapping[str, str],
) -> None:
    info_xref, existing_keys = _custom_string_info_keys(document)
    if info_xref is None:
        if not custom_info_dict:
            return
        msg = "PDF Info dictionary is unavailable."
        raise ValueError(msg)

    for removed_name in existing_keys.keys() - custom_info_dict.keys():
        document.xref_set_key(
            info_xref,
            existing_keys[removed_name],
            "null",
        )
    for name, value in custom_info_dict.items():
        pdf_key = existing_keys.get(name, name)
        document.xref_set_key(info_xref, pdf_key, pymupdf.get_pdf_str(value))


def read_document_metadata(
    document: pymupdf.Document,
) -> tuple[dict[str, str], dict[str, str], str]:
    """Return standard, custom, and raw XMP document metadata."""
    raw_metadata = document.metadata or {}
    info_dict = {
        key: _coerce_metadata_value(raw_metadata.get(key))
        for key in _INFO_METADATA_KEYS
    }
    custom_info_dict = _read_custom_info_metadata(document)
    xmp_xml = _coerce_metadata_value(document.get_xml_metadata())
    return info_dict, custom_info_dict, xmp_xml


def write_document_metadata(
    document: pymupdf.Document,
    *,
    info_dict: Mapping[str, str],
    custom_info_dict: Mapping[str, str],
    xmp_xml: str,
) -> None:
    """Update standard, custom, and raw XMP document metadata."""
    _validate_metadata(
        info_dict=info_dict,
        custom_info_dict=custom_info_dict,
        xmp_xml=xmp_xml,
    )
    raw_metadata = dict(document.metadata or {})
    for key in _EDITABLE_INFO_METADATA_KEYS:
        raw_metadata[key] = info_dict.get(key, "")
    document.set_metadata(raw_metadata)
    _write_custom_info_metadata(document, custom_info_dict)
    if xmp_xml:
        document.set_xml_metadata(xmp_xml)
        return

    if document.get_xml_metadata():
        document.del_xml_metadata()


def render_page(
    document: pymupdf.Document,
    page_index: int,
    *,
    zoom: float,
    device_pixel_ratio: float = 1.0,
) -> pymupdf.Pixmap:
    """Render a page at a specific zoom level."""
    page = document.load_page(page_index)
    scale = zoom * max(device_pixel_ratio, 1.0)
    matrix = pymupdf.Matrix(scale, scale)
    return page.get_pixmap(matrix=matrix, alpha=False)


def render_thumbnail(
    document: pymupdf.Document,
    page_index: int,
    *,
    max_dimension: int = 160,
) -> pymupdf.Pixmap:
    """Render a page thumbnail constrained by the larger dimension."""
    page = document.load_page(page_index)
    width_scale = max_dimension / max(page.rect.width, 1)
    height_scale = max_dimension / max(page.rect.height, 1)
    scale = min(width_scale, height_scale)
    matrix = pymupdf.Matrix(scale, scale)
    return page.get_pixmap(matrix=matrix, alpha=False)


def page_links(
    document: pymupdf.Document,
    page_index: int,
    *,
    zoom: float,
) -> list[PdfPageLink]:
    """Return clickable link hotspots scaled into the current render space."""
    page = document.load_page(page_index)
    links: list[PdfPageLink] = []
    for link in page.get_links():
        link_rect = link.get("from")
        if not isinstance(link_rect, pymupdf.Rect) or link_rect.is_empty:
            continue

        uri = _normalized_link_uri(link)
        file_path = _normalized_link_file(link)
        target_page_index = _normalized_target_page(link)
        target_point = _normalized_target_point(link.get("to"))
        target_zoom = _normalized_target_zoom(link)
        target_fit = _normalized_target_fit(
            target_page_index=target_page_index,
            target_point=target_point,
            target_zoom=target_zoom,
        )
        named_destination = _normalized_named_destination(link)
        if (
            uri is None
            and file_path is None
            and target_page_index is None
            and named_destination is None
        ):
            continue

        display_rect = link_rect * page.rotation_matrix
        links.append(
            PdfPageLink(
                bounds=(
                    display_rect.x0 * zoom,
                    display_rect.y0 * zoom,
                    display_rect.x1 * zoom,
                    display_rect.y1 * zoom,
                ),
                target_page_index=target_page_index,
                target_point=target_point,
                target_zoom=target_zoom,
                target_fit=target_fit,
                named_destination=named_destination,
                uri=uri,
                file_path=file_path,
            ),
        )

    return links


def _normalized_link_uri(link: dict[str, object]) -> str | None:
    uri = link.get("uri")
    if not isinstance(uri, str):
        return None

    stripped_uri = uri.strip()
    if stripped_uri.startswith(_NAMED_DESTINATION_PREFIX):
        return None

    return stripped_uri or None


def _normalized_link_file(link: dict[str, object]) -> str | None:
    file_path = link.get("file")
    if not isinstance(file_path, str):
        return None

    stripped_path = file_path.strip()
    return stripped_path or None


def _normalized_target_page(link: dict[str, object]) -> int | None:
    target_page_index = link.get("page")
    if not isinstance(target_page_index, int) or target_page_index < 0:
        return None

    return target_page_index


def _normalized_named_destination(link: dict[str, object]) -> str | None:
    named_destination = link.get("nameddest")
    if isinstance(named_destination, str):
        stripped_name = named_destination.strip()
        if stripped_name:
            return stripped_name

    uri = link.get("uri")
    if not isinstance(uri, str):
        return None

    stripped_uri = uri.strip()
    if not stripped_uri.startswith(_NAMED_DESTINATION_PREFIX):
        return None

    stripped_name = stripped_uri.removeprefix(_NAMED_DESTINATION_PREFIX).strip()
    return stripped_name or None


def _normalized_target_point(
    target_point: object,
) -> tuple[float, float] | None:
    if not isinstance(target_point, pymupdf.Point):
        return None

    return (target_point.x, target_point.y)


def _normalized_target_zoom(link: dict[str, object]) -> float | None:
    target_zoom = link.get("zoom")
    if not isinstance(target_zoom, (float, int)) or target_zoom <= 0:
        return None

    return float(target_zoom)


def _normalized_target_fit(
    *,
    target_page_index: int | None,
    target_point: tuple[float, float] | None,
    target_zoom: float | None,
) -> str | None:
    if target_page_index is None:
        return None

    if target_point is not None or target_zoom is not None:
        return "XYZ"

    return "Fit"


def _validate_metadata(
    *,
    info_dict: Mapping[str, str],
    custom_info_dict: Mapping[str, str],
    xmp_xml: str,
) -> None:
    for date_key in ("creationDate", "modDate"):
        _validate_pdf_date(date_key, info_dict.get(date_key, ""))

    trapped = info_dict.get("trapped", "")
    if trapped not in _TRAPPED_VALUES:
        msg = "trapped must be True, False, or Unknown."
        raise ValueError(msg)

    _validate_custom_info_metadata(custom_info_dict)

    if xmp_xml:
        _validate_xmp_xml(xmp_xml)


def _validate_custom_info_metadata(
    custom_info_dict: Mapping[str, str],
) -> None:
    for name, value in custom_info_dict.items():
        if not name:
            msg = "Custom property names cannot be empty."
            raise ValueError(msg)
        if _CUSTOM_INFO_NAME_RE.fullmatch(name) is None:
            msg = (
                "Custom property names may contain only letters, numbers, "
                "periods, underscores, and hyphens."
            )
            raise ValueError(msg)
        if name in _STANDARD_INFO_PDF_KEYS:
            msg = f"{name} is a standard PDF property name."
            raise ValueError(msg)
        if not isinstance(value, str):
            msg = f"Custom property {name} must have a text value."
            raise TypeError(msg)


def _validate_pdf_date(field_name: str, date_text: str) -> None:
    if not date_text:
        return

    if _PDF_DATE_RE.fullmatch(date_text):
        return

    msg = f"{field_name} must use PDF date syntax."
    raise ValueError(msg)


def _validate_xmp_xml(xmp_xml: str) -> None:
    xml_body = _XPACKET_PI_RE.sub("", xmp_xml).strip()
    reader = QXmlStreamReader(xml_body)
    saw_start_element = False
    while not reader.atEnd():
        token = reader.readNext()
        if token == QXmlStreamReader.TokenType.StartElement:
            saw_start_element = True

    if reader.hasError() or not saw_start_element:
        msg = "XMP metadata must be valid XML."
        raise ValueError(msg)


def page_link_target_position(
    document: pymupdf.Document,
    *,
    target_page_index: int | None,
    target_point: tuple[float, float] | None,
    zoom: float,
) -> tuple[float, float] | None:
    """Resolve a PDF-space destination point into display coordinates."""
    if target_page_index is None or target_point is None:
        return None

    target_page = document.load_page(target_page_index)
    pdf_target_point = pymupdf.Point(target_point)
    display_point = (
        pdf_target_point * target_page.transformation_matrix
    ) * target_page.rotation_matrix
    return (display_point.x * zoom, display_point.y * zoom)


def pdf_point_for_display_position(
    document: pymupdf.Document,
    *,
    page_index: int,
    position: tuple[float, float],
    zoom: float,
) -> tuple[float, float] | None:
    """Resolve a display-space position back into its PDF-space point.

    - Exact inverse of `page_link_target_position`, so a round trip at any
      zoom or rotation returns the original point.
    """
    if zoom <= 0:
        return None

    page = document.load_page(page_index)
    display_point = pymupdf.Point(position[0] / zoom, position[1] / zoom)
    # PyMuPDF types these as Matrix | tuple; Matrix() normalizes both so
    # the inverse operator is well-defined.
    rotation = pymupdf.Matrix(page.rotation_matrix)
    transformation = pymupdf.Matrix(page.transformation_matrix)
    pdf_point = (display_point * ~rotation) * ~transformation
    return (pdf_point.x, pdf_point.y)


def resolve_page_link_target(
    document: pymupdf.Document,
    *,
    target_page_index: int | None,
    target_point: tuple[float, float] | None,
    named_destination: str | None,
    zoom: float,
) -> tuple[int, tuple[float, float] | None] | None:
    """Resolve direct or named PDF link targets into page and position."""
    if target_page_index is not None:
        return (
            target_page_index,
            page_link_target_position(
                document,
                target_page_index=target_page_index,
                target_point=target_point,
                zoom=zoom,
            ),
        )

    if named_destination is None:
        return None

    resolved_page_index, target_x, target_y = document.resolve_link(
        f"{_NAMED_DESTINATION_PREFIX}{named_destination}",
    )
    if not isinstance(resolved_page_index, int) or resolved_page_index < 0:
        return None

    target_position = page_link_target_position(
        document,
        target_page_index=resolved_page_index,
        target_point=(float(target_x), float(target_y)),
        zoom=zoom,
    )
    return resolved_page_index, target_position


def page_size_points(
    document: pymupdf.Document,
    page_index: int,
) -> tuple[float, float]:
    """Return one page's unscaled size in PDF points."""
    page = document.load_page(page_index)
    return (float(page.rect.width), float(page.rect.height))


def display_size_for_page_size(
    page_size: tuple[float, float],
    *,
    zoom: float,
) -> tuple[int, int]:
    """Return the rendered pixel size for an unscaled page size."""
    page_width, page_height = page_size
    return (
        max(int(page_width * zoom), 1),
        max(int(page_height * zoom), 1),
    )


def page_display_size(
    document: pymupdf.Document,
    page_index: int,
    *,
    zoom: float,
) -> tuple[int, int]:
    """Return the rendered page size for a given zoom level."""
    return display_size_for_page_size(
        page_size_points(document, page_index),
        zoom=zoom,
    )
