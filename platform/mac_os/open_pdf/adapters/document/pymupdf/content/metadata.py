"""PyMuPDF metadata operations."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pymupdf
from PySide6.QtCore import QXmlStreamReader

if TYPE_CHECKING:
    from collections.abc import Mapping


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
