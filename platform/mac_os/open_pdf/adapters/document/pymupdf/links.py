"""PyMuPDF links operations."""

from __future__ import annotations

import pymupdf

from open_pdf.domains.document.models import PdfPageLink

_NAMED_DESTINATION_PREFIX = "#nameddest="


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
