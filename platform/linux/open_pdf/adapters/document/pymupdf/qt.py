"""Adapters that translate PyMuPDF rendering objects into Qt objects."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QImage, QPixmap

if TYPE_CHECKING:
    import pymupdf


def qimage_from_pymupdf(rendered_page: pymupdf.Pixmap) -> QImage:
    """Convert a PyMuPDF pixmap into a detached Qt image."""
    image_format = QImage.Format.Format_RGB888
    if rendered_page.n == 1:
        image_format = QImage.Format.Format_Grayscale8

    image = QImage(
        rendered_page.samples,
        int(rendered_page.w),
        int(rendered_page.h),
        int(rendered_page.stride),
        image_format,
    )
    return image.copy()


def pixmap_from_pymupdf(rendered_page: pymupdf.Pixmap) -> QPixmap:
    """Convert a PyMuPDF pixmap into a detached Qt pixmap."""
    return QPixmap.fromImage(qimage_from_pymupdf(rendered_page))
