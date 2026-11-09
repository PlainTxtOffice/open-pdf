"""PyMuPDF rendering operations."""

from __future__ import annotations

import pymupdf


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
