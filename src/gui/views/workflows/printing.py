"""PDF printing workflow for the main viewer window."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter
from PySide6.QtPrintSupport import (
    QAbstractPrintDialog,
    QPrintDialog,
    QPrinter,
)
from PySide6.QtWidgets import QDialog, QWidget

from src.adapters.document.pymupdf.qt import qimage_from_pymupdf
from src.domains.document.errors import PDF_IO_ERRORS

if TYPE_CHECKING:
    from PySide6.QtWidgets import QStatusBar

    from src.domains.document.reader import PdfDocument


class _PrintingWorkflowHost(Protocol):
    """Describe the main-window API required by the printing workflow."""

    _document: PdfDocument

    def _show_error(self, message: str) -> None: ...

    def statusBar(self) -> QStatusBar: ...  # noqa: N802

    def _selected_print_page_indexes(self, printer: QPrinter) -> range: ...

    @staticmethod
    def _advance_printer_page(
        *,
        printer: QPrinter,
        printed_page_index: int,
    ) -> None: ...

    @staticmethod
    def _print_target_rect(
        *,
        page_rect: QRectF,
        image_width: int,
        image_height: int,
    ) -> QRectF: ...


class PrintingWorkflowMixin:
    """Coordinate print selection, rendering, and painter output."""

    def _print_document(self: _PrintingWorkflowHost) -> None:
        if not self._document.has_document():
            return

        page_count = self._document.state.page_count
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, cast("QWidget", self))
        if page_count > 0:
            dialog.setMinMax(1, page_count)
        if page_count > 1:
            dialog.setOption(
                QAbstractPrintDialog.PrintDialogOption.PrintPageRange,
            )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        render_zoom = max(printer.resolution() / 72.0, 1.0)
        painter = QPainter()
        if not painter.begin(printer):
            self._show_error("Failed to start the printer.")
            return

        try:
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            for printed_page_index, page_index in enumerate(
                self._selected_print_page_indexes(printer),
            ):
                self._advance_printer_page(
                    printer=printer,
                    printed_page_index=printed_page_index,
                )
                image = qimage_from_pymupdf(
                    self._document.render_page_at_zoom(
                        page_index,
                        zoom=render_zoom,
                    ),
                )
                target_rect = self._print_target_rect(
                    page_rect=QRectF(page_rect),
                    image_width=image.width(),
                    image_height=image.height(),
                )
                painter.drawImage(target_rect, image)
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to print PDF:\n{error}")
            return
        finally:
            painter.end()

        self.statusBar().showMessage("Sent document to printer", 5000)

    @staticmethod
    def _advance_printer_page(
        *,
        printer: QPrinter,
        printed_page_index: int,
    ) -> None:
        if printed_page_index == 0 or printer.newPage():
            return
        msg = "The printer could not advance to the next page."
        raise RuntimeError(msg)

    def _selected_print_page_indexes(
        self: _PrintingWorkflowHost,
        printer: QPrinter,
    ) -> range:
        page_count = self._document.state.page_count
        if page_count <= 0:
            return range(0)

        print_range = printer.printRange()
        if print_range == QAbstractPrintDialog.PrintRange.PageRange:
            first_page = max(printer.fromPage(), 1)
            last_page = min(printer.toPage(), page_count)
            if last_page < first_page:
                return range(0)
            return range(first_page - 1, last_page)

        if print_range in {
            QAbstractPrintDialog.PrintRange.CurrentPage,
            QAbstractPrintDialog.PrintRange.Selection,
        }:
            current_page_index = self._document.state.current_page_index
            return range(current_page_index, current_page_index + 1)
        return range(page_count)

    @staticmethod
    def _print_target_rect(
        *,
        page_rect: QRectF,
        image_width: int,
        image_height: int,
    ) -> QRectF:
        width_scale = page_rect.width() / max(image_width, 1)
        height_scale = page_rect.height() / max(image_height, 1)
        scale = min(width_scale, height_scale)
        target_width = image_width * scale
        target_height = image_height * scale
        return QRectF(
            page_rect.x() + ((page_rect.width() - target_width) / 2),
            page_rect.y() + ((page_rect.height() - target_height) / 2),
            target_width,
            target_height,
        )
