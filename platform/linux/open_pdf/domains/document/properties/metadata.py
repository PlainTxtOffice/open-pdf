"""Normalize edits to document metadata without accessing a PDF engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

from open_pdf.domains.document.models import PdfMetadata

if TYPE_CHECKING:
    from collections.abc import Mapping


def normalize_metadata(
    current: PdfMetadata,
    *,
    info_dict: Mapping[str, str],
    custom_info_dict: Mapping[str, str] | None,
    xmp_xml: str,
) -> PdfMetadata:
    """Trim edited fields and retain custom properties when omitted."""
    return PdfMetadata(
        info_dict={key: value.strip() for key, value in info_dict.items()},
        custom_info_dict=(
            current.custom_info_dict
            if custom_info_dict is None
            else {
                key.strip(): value.strip()
                for key, value in custom_info_dict.items()
            }
        ),
        xmp_xml=xmp_xml.strip(),
    )
