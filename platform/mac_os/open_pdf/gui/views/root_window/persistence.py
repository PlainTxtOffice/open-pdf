"""Presentation mapping for persisted desktop preferences."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from open_pdf.gui.models.window_state import PaneSettings

if TYPE_CHECKING:
    from pathlib import Path

    from PySide6.QtGui import QAction

    from open_pdf.adapters.persistence.desktop import DesktopPersistence


logger = logging.getLogger(__name__)


class _PersistenceHost(Protocol):
    """Describe the main-window API required by PersistenceMixin."""

    _persistence: DesktopPersistence
    _is_restoring_pane_visibility: bool
    _is_text_selection_mode: bool
    _thumbnails_on_left: bool
    _bookmarks_pane_action: QAction
    _thumbnails_pane_action: QAction
    _text_pane_action: QAction
    _notes_pane_action: QAction
    _browse_mouse_mode_action: QAction
    _text_selection_mouse_mode_action: QAction
    _bookmarks_left_side_action: QAction
    _thumbnails_left_side_action: QAction

    def _apply_text_selection_mode(self) -> None: ...
    def _apply_side_pane_layout(self) -> None: ...
    def _load_pane_visibility_settings(self) -> PaneSettings: ...


class PersistenceMixin:
    """Map persisted desktop preferences to presentation state."""

    def _restore_pane_visibility_settings(self: _PersistenceHost) -> None:
        settings = self._load_pane_visibility_settings()
        self._is_restoring_pane_visibility = True
        try:
            self._bookmarks_pane_action.setChecked(settings.bookmarks_visible)
            self._thumbnails_pane_action.setChecked(settings.thumbnails_visible)
            self._text_pane_action.setChecked(settings.text_visible)
            self._notes_pane_action.setChecked(settings.notes_visible)
            self._is_text_selection_mode = True
            self._browse_mouse_mode_action.setChecked(True)
            self._text_selection_mouse_mode_action.setChecked(False)
            self._apply_text_selection_mode()
            self._thumbnails_on_left = settings.thumbnails_on_left
            self._bookmarks_left_side_action.setChecked(
                not self._thumbnails_on_left,
            )
            self._thumbnails_left_side_action.setChecked(
                self._thumbnails_on_left,
            )
            self._apply_side_pane_layout()
        finally:
            self._is_restoring_pane_visibility = False

    def _persist_pane_visibility_settings(self: _PersistenceHost) -> None:
        if self._is_restoring_pane_visibility:
            return
        settings = PaneSettings(
            bookmarks_visible=self._bookmarks_pane_action.isChecked(),
            thumbnails_visible=self._thumbnails_pane_action.isChecked(),
            text_visible=self._text_pane_action.isChecked(),
            notes_visible=self._notes_pane_action.isChecked(),
            text_selection_mode=self._is_text_selection_mode,
            thumbnails_on_left=self._thumbnails_on_left,
        )
        self._persistence.save_preferences(settings.as_dict())

    def _load_pane_visibility_settings(self: _PersistenceHost) -> PaneSettings:
        return PaneSettings.from_dict(self._persistence.load_preferences())

    def _remember_document_password(
        self: _PersistenceHost,
        *,
        path: Path,
        password: str,
    ) -> None:
        if not self._persistence.remember_password(
            path=path,
            password=password,
        ):
            logger.warning(
                "Remembered PDF passwords are unavailable on this platform.",
            )

    def _recall_document_password(
        self: _PersistenceHost,
        path: Path,
    ) -> str | None:
        return self._persistence.recall_password(path)

    def _forget_document_password(self: _PersistenceHost, path: Path) -> None:
        self._persistence.forget_password(path)

    def _move_remembered_document_password(
        self: _PersistenceHost,
        *,
        source_path: Path,
        target_path: Path,
    ) -> None:
        self._persistence.move_password(
            source_path=source_path,
            target_path=target_path,
        )
