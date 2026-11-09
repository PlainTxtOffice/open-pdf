"""Toolbar construction for the PySide6 PDF window."""

# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QStyle,
    QToolBar,
    QToolButton,
    QWidget,
)

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QLineEdit, QSpinBox


class _ToolbarWindow(Protocol):
    """Describe the host window state required by toolbar helpers."""

    _open_action: QAction
    _save_action: QAction
    _save_as_action: QAction
    _history_back_shortcut_action: QAction
    _history_forward_shortcut_action: QAction
    _previous_page_shortcut_action: QAction
    _next_page_shortcut_action: QAction
    _zoom_out_shortcut_action: QAction
    _zoom_in_shortcut_action: QAction
    _actual_size_action: QAction
    _fit_width_action: QAction
    _fit_page_action: QAction
    _single_page_view_action: QAction
    _find_action: QAction
    _previous_match_action: QAction
    _next_match_action: QAction
    _edit_pdf_action: QAction
    _remove_selected_text_action: QAction
    _rotate_right_action: QAction
    _mouse_mode_indicator: QToolButton
    _page_selector: QSpinBox
    _search_input: QLineEdit
    _search_bar: QWidget
    _search_status_label: QLabel

    # Positional-only: Qt declares these with unnamed parameters, and a
    # named parameter here makes MainWindow fail the protocol.
    def addAction(self, action: QAction, /) -> None: ...  # noqa: N802

    def addToolBar(self, toolbar: QToolBar, /) -> None: ...  # noqa: N802

    def _choose_pdf(self) -> None: ...

    def _save(self) -> None: ...

    def _save_as(self) -> None: ...

    def _go_back_history(self) -> None: ...

    def _go_forward_history(self) -> None: ...

    def _show_previous_page(self) -> None: ...

    def _show_next_page(self) -> None: ...

    def _zoom_out(self) -> None: ...

    def _zoom_in(self) -> None: ...

    def _zoom_to_actual_size(self) -> None: ...

    def _zoom_fit_width(self) -> None: ...

    def _zoom_fit_page(self) -> None: ...

    def _set_single_page_view_enabled(self, *, enabled: bool) -> None: ...

    def _run_search(self) -> None: ...

    def _focus_search_input(self) -> None: ...

    def _hide_search_bar(self) -> None: ...

    def _update_search_bar_state(self) -> None: ...

    def _show_previous_match(self) -> None: ...

    def _show_next_match(self) -> None: ...

    def _enter_pdf_edit_mode(self) -> None: ...

    def _remove_selected_text(self) -> None: ...

    def _rotate_current_page(self) -> None: ...


def build_toolbar(window: _ToolbarWindow) -> None:
    """Build the main toolbar and its action groups."""
    toolbar = QToolBar("Main")
    toolbar.setMovable(False)
    window.addToolBar(toolbar)

    add_file_actions(window)
    add_history_actions(window)
    add_navigation_actions(window, toolbar)
    add_zoom_preset_actions(window)
    add_view_mode_actions(window)
    add_pdf_edit_actions(window, toolbar)
    toolbar.addSeparator()
    add_fit_page_action(window, toolbar)
    toolbar.addSeparator()
    add_zoom_actions(window)
    add_search_actions(window, toolbar)
    add_mouse_mode_indicator(window, toolbar)
    add_rotation_actions(window)


def add_file_actions(window: _ToolbarWindow) -> None:
    """Create the file actions shared by the menu bar."""
    action_parent = cast("QObject", window)

    window._open_action = QAction("Open", action_parent)
    window._open_action.triggered.connect(window._choose_pdf)

    window._save_action = QAction("Save", action_parent)
    window._save_action.triggered.connect(window._save)

    window._save_as_action = QAction("Save As", action_parent)
    window._save_as_action.triggered.connect(window._save_as)


def add_history_actions(window: _ToolbarWindow) -> None:
    """Create page-history actions without toolbar buttons."""
    action_parent = cast("QObject", window)

    window._history_back_shortcut_action = QAction("Back", action_parent)
    window._history_back_shortcut_action.triggered.connect(
        window._go_back_history,
    )

    window._history_forward_shortcut_action = QAction(
        "Forward",
        action_parent,
    )
    window._history_forward_shortcut_action.triggered.connect(
        window._go_forward_history,
    )


def add_navigation_actions(window: _ToolbarWindow, toolbar: QToolBar) -> None:
    """Create page-step actions and add only the page selector to toolbar."""
    action_parent = cast("QObject", window)

    window._previous_page_shortcut_action = QAction(
        "Previous",
        action_parent,
    )
    window._previous_page_shortcut_action.triggered.connect(
        window._show_previous_page,
    )
    window.addAction(window._previous_page_shortcut_action)

    window._next_page_shortcut_action = QAction("Next", action_parent)
    window._next_page_shortcut_action.triggered.connect(
        window._show_next_page,
    )
    window.addAction(window._next_page_shortcut_action)

    toolbar.addWidget(window._page_selector)


def add_fit_page_action(window: _ToolbarWindow, toolbar: QToolBar) -> None:
    """Add a fit-page button to the toolbar."""
    fit_page_icon = toolbar.style().standardIcon(
        QStyle.StandardPixmap.SP_TitleBarMaxButton,
    )
    window._fit_page_action.setIcon(fit_page_icon)
    toolbar.addAction(window._fit_page_action)


def add_zoom_actions(window: _ToolbarWindow) -> None:
    """Create zoom shortcut actions without toolbar buttons."""
    action_parent = cast("QObject", window)

    window._zoom_out_shortcut_action = QAction("Zoom Out", action_parent)
    window._zoom_out_shortcut_action.triggered.connect(window._zoom_out)
    window.addAction(window._zoom_out_shortcut_action)

    window._zoom_in_shortcut_action = QAction("Zoom In", action_parent)
    window._zoom_in_shortcut_action.triggered.connect(window._zoom_in)
    window.addAction(window._zoom_in_shortcut_action)


def add_zoom_preset_actions(window: _ToolbarWindow) -> None:
    """Create the zoom preset actions used by the View menu."""
    action_parent = cast("QObject", window)

    window._actual_size_action = QAction("Actual Size", action_parent)
    window._actual_size_action.triggered.connect(window._zoom_to_actual_size)

    window._fit_width_action = QAction("Fit Width", action_parent)
    window._fit_width_action.triggered.connect(window._zoom_fit_width)

    window._fit_page_action = QAction("Fit Page", action_parent)
    window._fit_page_action.triggered.connect(window._zoom_fit_page)


def add_view_mode_actions(window: _ToolbarWindow) -> None:
    """Create view-mode actions used by the View menu."""
    action_parent = cast("QObject", window)

    window._single_page_view_action = QAction(
        "Single Page View",
        action_parent,
    )
    window._single_page_view_action.setCheckable(True)
    window._single_page_view_action.toggled.connect(
        lambda checked: window._set_single_page_view_enabled(
            enabled=checked,
        ),
    )


def add_pdf_edit_actions(window: _ToolbarWindow, toolbar: QToolBar) -> None:
    """Create PDF-editing actions and expose the entry action in the toolbar."""
    action_parent = cast("QObject", window)

    window._edit_pdf_action = QAction("Edit PDF", action_parent)
    window._edit_pdf_action.setToolTip("Enter PDF text-edit mode")
    window._edit_pdf_action.triggered.connect(window._enter_pdf_edit_mode)

    window._remove_selected_text_action = QAction(
        "Remove Content",
        action_parent,
    )
    window._remove_selected_text_action.triggered.connect(
        window._remove_selected_text,
    )

    edit_pdf_button = QToolButton(toolbar)
    edit_pdf_button.setObjectName("edit-pdf-button")
    edit_pdf_button.setAccessibleName("Edit PDF")
    edit_pdf_button.setToolButtonStyle(
        Qt.ToolButtonStyle.ToolButtonTextOnly,
    )
    edit_pdf_button.setDefaultAction(window._edit_pdf_action)
    toolbar.addWidget(edit_pdf_button)


def add_search_actions(window: _ToolbarWindow, toolbar: QToolBar) -> None:
    """Create a hidden VS Code-style search strip for the toolbar."""
    action_parent = cast("QObject", window)

    window._find_action = QAction("Find", action_parent)
    window._find_action.setShortcut(QKeySequence.StandardKey.Find)
    window._find_action.triggered.connect(window._focus_search_input)

    window._previous_match_action = QAction("Previous Match", action_parent)
    window._previous_match_action.setIcon(
        toolbar.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp),
    )
    window._previous_match_action.triggered.connect(
        window._show_previous_match,
    )

    window._next_match_action = QAction("Next Match", action_parent)
    window._next_match_action.setIcon(
        toolbar.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown),
    )
    window._next_match_action.triggered.connect(window._show_next_match)

    search_bar = QWidget(toolbar)
    search_bar_layout = QHBoxLayout(search_bar)
    search_bar_layout.setContentsMargins(0, 0, 0, 0)
    search_bar_layout.setSpacing(4)

    window._search_input.setPlaceholderText("Find")
    window._search_input.setMinimumWidth(220)
    search_bar_layout.addWidget(window._search_input)

    window._search_status_label = QLabel(search_bar)
    search_bar_layout.addWidget(window._search_status_label)

    previous_button = QToolButton(search_bar)
    previous_button.setAutoRaise(True)
    previous_button.setDefaultAction(window._previous_match_action)
    search_bar_layout.addWidget(previous_button)

    next_button = QToolButton(search_bar)
    next_button.setAutoRaise(True)
    next_button.setDefaultAction(window._next_match_action)
    search_bar_layout.addWidget(next_button)

    close_button = QToolButton(search_bar)
    close_button.setAutoRaise(True)
    close_button.setIcon(
        toolbar.style().standardIcon(
            QStyle.StandardPixmap.SP_DialogCloseButton,
        ),
    )
    close_button.setToolTip("Close Search")
    close_button.clicked.connect(window._hide_search_bar)
    search_bar_layout.addWidget(close_button)

    window._search_bar = search_bar
    window._search_bar.hide()
    window._update_search_bar_state()
    toolbar.addWidget(window._search_bar)


def add_mouse_mode_indicator(window: _ToolbarWindow, toolbar: QToolBar) -> None:
    """Show the current mouse mode in the toolbar."""
    toolbar.addSeparator()
    toolbar.addWidget(window._mouse_mode_indicator)


def add_rotation_actions(window: _ToolbarWindow) -> None:
    """Create page-rotation actions for menus without toolbar buttons."""
    action_parent = cast("QObject", window)

    window._rotate_right_action = QAction("Rotate Right", action_parent)
    window._rotate_right_action.triggered.connect(
        window._rotate_current_page,
    )
