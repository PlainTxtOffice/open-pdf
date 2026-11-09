"""Presentation workflow for renaming the active PDF file."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol, cast

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

if TYPE_CHECKING:
    from pathlib import Path

    from PySide6.QtWidgets import QStatusBar

    from open_pdf.application.document.rename import (
        DocumentFileRenamer,
        RenameDestination,
    )
    from open_pdf.application.document.session import PdfDocument


logger = logging.getLogger(__name__)


class _FileRenameWorkflowHost(Protocol):
    """Describe the main-window API required by FileRenameWorkflowMixin."""

    _document: PdfDocument
    _file_renamer: DocumentFileRenamer

    @staticmethod
    def _normalize_document_path(path: Path) -> Path: ...
    def _show_error(self, message: str) -> None: ...
    def _move_remembered_document_password(
        self,
        *,
        source_path: Path,
        target_path: Path,
    ) -> None: ...
    def _refresh_actions(self) -> None: ...
    def _release_background_render_handles(self) -> None: ...
    def _update_status_bar(self) -> None: ...
    def statusBar(self) -> QStatusBar: ...  # noqa: N802
    def _choose_rename_destination(
        self,
        source_path: Path,
    ) -> RenameDestination | None: ...

    def _confirm_rename_file_overwrite(
        self,
        target_path: Path,
    ) -> bool: ...

    def _perform_file_rename(
        self,
        *,
        source_path: Path,
        destination: RenameDestination,
    ) -> None: ...


class FileRenameWorkflowMixin:
    """Present the rename dialog and report application-service results."""

    def _rename_file(self: _FileRenameWorkflowHost) -> None:
        source_path = self._document.source_path
        if not self._document.has_document() or source_path is None:
            return
        destination = self._choose_rename_destination(source_path)
        if destination is not None:
            self._perform_file_rename(
                source_path=source_path,
                destination=destination,
            )

    def _choose_rename_destination(
        self: _FileRenameWorkflowHost,
        source_path: Path,
    ) -> RenameDestination | None:
        chosen_path, _ = QFileDialog.getSaveFileName(
            cast("QWidget", self),
            "Rename File",
            str(source_path),
            "PDF Files (*.pdf)",
        )
        if not chosen_path:
            return None

        target_path = type(source_path)(chosen_path)
        if self._normalize_document_path(target_path) == (
            self._normalize_document_path(source_path)
        ):
            return None
        if self._file_renamer.destination_exists(target_path) and not (
            self._confirm_rename_file_overwrite(target_path)
        ):
            return None

        try:
            return self._file_renamer.prepare_destination(target_path)
        except OSError as error:
            self._show_error(
                "Failed to prepare the existing destination file for "
                f"replacement:\n{error}",
            )
            return None

    def _perform_file_rename(
        self: _FileRenameWorkflowHost,
        *,
        source_path: Path,
        destination: RenameDestination,
    ) -> None:
        rename_error = self._file_renamer.save_document(
            document=self._document,
            destination=destination,
        )
        if rename_error is not None:
            self._show_error(rename_error)
            return

        self._move_remembered_document_password(
            source_path=source_path,
            target_path=destination.target_path,
        )
        self._release_background_render_handles()
        cleanup_errors = self._file_renamer.cleanup(
            source_path=source_path,
            destination=destination,
        )
        self._refresh_actions()
        self._update_status_bar()
        self.statusBar().showMessage(
            f"Renamed to {destination.target_path.name}",
            5000,
        )
        if cleanup_errors:
            logger.warning(
                "Rename to %s completed with cleanup warnings: %s",
                destination.target_path,
                cleanup_errors,
            )
            QMessageBox.warning(
                cast("QWidget", self),
                "Open PDF",
                "Renamed the PDF, but cleanup was incomplete:\n\n"
                + "\n\n".join(cleanup_errors),
            )

    def _confirm_rename_file_overwrite(
        self: _FileRenameWorkflowHost,
        target_path: Path,
    ) -> bool:
        response = QMessageBox.question(
            cast("QWidget", self),
            "Overwrite Existing File",
            f"{target_path.name} already exists. Replace it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return response == QMessageBox.StandardButton.Yes
