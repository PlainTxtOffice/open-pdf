"""Main application window for the PDF viewer."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QEvent,
    QObject,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QGuiApplication,
    QKeyEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QStyle,
    QTabBar,
    QTextEdit,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from open_pdf.adapters.document.errors import PDF_IO_ERRORS
from open_pdf.adapters.ocr.results import OcrResultStore, local_ocr_result_store
from open_pdf.adapters.persistence.desktop import DesktopPersistence
from open_pdf.application.document.rename import DocumentFileRenamer
from open_pdf.application.document.session import PdfDocument
from open_pdf.config.path_handler import DATA_DIR
from open_pdf.domains.document.errors import (
    IncorrectPasswordError,
    PasswordRequiredError,
)
from open_pdf.gui.models.window_state import (
    OcrState,
    RenderGenerations,
    SearchState,
    SyncGuards,
)
from open_pdf.gui.ocr.workflow import OcrWorkflowMixin
from open_pdf.gui.views.dialogs.properties_dialog import (
    DocumentPropertyValues,
    prompt_document_properties,
)
from open_pdf.gui.views.menus.file_menu_bar import build_menu_bar
from open_pdf.gui.views.menus.help.about_open_pdf import (
    show_about_open_pdf_dialog,
)
from open_pdf.gui.views.menus.toolbars import build_toolbar
from open_pdf.gui.views.rendering.page_geometry import PageGeometryMixin
from open_pdf.gui.views.rendering.page_render_cache import PageRenderCacheMixin
from open_pdf.gui.views.rendering.render_handle_cache import RENDER_HANDLE_CACHE
from open_pdf.gui.views.rendering.selection import PageSelectionMixin
from open_pdf.gui.views.rendering.zoom.interaction import (
    ZoomInteractionMixin,
    ZoomScrollRestore,
)
from open_pdf.gui.views.rendering.zoom.preview import (
    ZOOM_SETTLE_INTERVAL_MS,
    ZoomPreviewGesture,
    ZoomPreviewMixin,
)
from open_pdf.gui.views.root_window.document_sync import DocumentSyncMixin
from open_pdf.gui.views.root_window.navigation.bookmarks import (
    BookmarkNavigationMixin,
)
from open_pdf.gui.views.root_window.navigation.view_panes import ViewPaneMixin
from open_pdf.gui.views.root_window.panes.thumbnails import (
    ThumbnailNavigationMixin,
)
from open_pdf.gui.views.root_window.persistence import PersistenceMixin
from open_pdf.gui.views.root_window.tabs.document_tabs import DocumentTabsMixin
from open_pdf.gui.views.search.search_highlighting import SearchHighlightMixin
from open_pdf.gui.views.search.search_navigation import SearchNavigationMixin
from open_pdf.gui.views.workflows.file_rename import FileRenameWorkflowMixin
from open_pdf.gui.views.workflows.printing import PrintingWorkflowMixin
from open_pdf.gui.views.workflows.text_editing import TextEditingMixin

if TYPE_CHECKING:
    from open_pdf.adapters.ocr.backend import PdfOcrBackend
    from open_pdf.gui.models.document_session import DocumentSession


logger = logging.getLogger(__name__)

_PANE_SETTINGS_PATH = DATA_DIR / "ui-state.json"
_DOCUMENT_PASSWORDS_PATH = DATA_DIR / "document-passwords.json"
_OCR_CACHE_DIRECTORY = DATA_DIR / "ocr-cache"
_RENDER_HANDLE_RELEASE_TIMEOUT_MS = 5000


class _PreferredWidthPane(QWidget):
    """Side pane that starts at a preferred width but resizes via splitter."""

    def __init__(self, preferred_width: int) -> None:
        super().__init__()
        self._preferred_width = preferred_width

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._preferred_width, super().sizeHint().height())


class MainWindow(
    BookmarkNavigationMixin,
    TextEditingMixin,
    PageSelectionMixin,
    DocumentSyncMixin,
    DocumentTabsMixin,
    FileRenameWorkflowMixin,
    OcrWorkflowMixin,
    PageGeometryMixin,
    PageRenderCacheMixin,
    PersistenceMixin,
    PrintingWorkflowMixin,
    SearchHighlightMixin,
    SearchNavigationMixin,
    ThumbnailNavigationMixin,
    ViewPaneMixin,
    ZoomInteractionMixin,
    ZoomPreviewMixin,
    QMainWindow,
):
    """Desktop shell for viewing and lightly editing PDFs."""

    if TYPE_CHECKING:
        _open_action: QAction
        _save_action: QAction
        _save_as_action: QAction
        _run_ocr_page_action: QAction
        _run_ocr_document_action: QAction
        _rename_file_action: QAction
        _print_action: QAction
        _properties_action: QAction
        _close_tab_action: QAction
        _exit_action: QAction
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
        _insert_page_before_action: QAction
        _insert_page_after_action: QAction
        _rotate_right_action: QAction
        _bookmarks_pane_action: QAction
        _thumbnails_pane_action: QAction
        _text_pane_action: QAction
        _notes_pane_action: QAction
        _bookmarks_left_side_action: QAction
        _thumbnails_left_side_action: QAction
        _browse_mouse_mode_action: QAction
        _text_selection_mouse_mode_action: QAction
        _about_action: QAction
        _mouse_mode_indicator: QToolButton
        _move_page_up_button: QToolButton
        _move_page_down_button: QToolButton
        _search_bar: QWidget
        _search_status_label: QLabel
        _search_debounce_timer: QTimer
        _document_tabs: QTabBar
        _document_tabs_toolbar: QToolBar

    def __init__(
        self,
        *,
        initial_path: Path | None = None,
        ocr_backend: PdfOcrBackend | None = None,
        ocr_cache: OcrResultStore | None = None,
        ocr_unavailable_message: str | None = None,
    ) -> None:
        """Initialize the main PDF viewer window.

        - Builds the navigation, page, and search widgets before the window is
          shown.
        - Opens `initial_path` immediately when provided.
        """
        super().__init__()
        self._ocr_backend = ocr_backend
        self._ocr_cache = (
            ocr_cache
            if ocr_cache is not None
            else local_ocr_result_store(_OCR_CACHE_DIRECTORY)
        )
        self._ocr_unavailable_message = ocr_unavailable_message
        self._initialize_state()
        self._configure_window_shell()
        self._build_document_view()
        self._build_side_panes()
        content_splitter = self._build_content_splitter()
        self._build_central_splitter(
            content_splitter=content_splitter,
        )
        self._build_page_controls()
        self._build_toolbar()
        self._build_document_tabs()
        self._build_menu_bar()
        self._initialize_document_tabs()
        self._restore_pane_visibility_settings()
        self.setStatusBar(QStatusBar())
        self._refresh_actions()
        self._update_status_bar()

        if initial_path is not None:
            self._open_path_in_tab(initial_path)

    def _initialize_state(self) -> None:
        """Initialize transient viewer state used by the window."""
        self._document = self._new_document_reader()
        self._tab_sessions: list[DocumentSession] = []
        self._active_tab_index = -1
        self._ocr = OcrState()
        self._sync = SyncGuards()
        self._search = SearchState()
        self._generations = RenderGenerations()
        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.setInterval(200)
        self._search_debounce_timer.timeout.connect(
            self._run_search,
        )
        self._page_labels: list[QLabel] = []
        self._visible_page_indexes: list[int] = []
        self._pending_zoom_scroll_restore: ZoomScrollRestore | None = None
        self._zoom_preview_gesture: ZoomPreviewGesture | None = None
        self._zoom_settle_timer = QTimer(self)
        self._zoom_settle_timer.setSingleShot(True)
        self._zoom_settle_timer.setInterval(ZOOM_SETTLE_INTERVAL_MS)
        self._zoom_settle_timer.timeout.connect(
            self._settle_zoom_preview,
        )
        self._rendered_page_indexes: set[int] = set()
        self._pending_page_indexes: dict[int, int] = {}
        self._desired_page_indexes: set[int] = set()
        self._render_request_counter = 0
        self._render_request_lock = Lock()
        self._render_scope_generation = 0
        self._render_scope_page_indexes: frozenset[int] = frozenset()
        self._thumbnail_rendered_pages: set[int] = set()
        self._thumbnail_pending_pages: set[int] = set()
        self._thumbnail_rerender_timer = QTimer(self)
        self._thumbnail_rerender_timer.setSingleShot(True)
        self._thumbnail_rerender_timer.setInterval(200)
        self._thumbnail_rerender_timer.timeout.connect(
            self._rerender_thumbnails,
        )
        self._words_loaded_pages: set[int] = set()
        self._page_top_offsets: list[int] = []
        self._page_bottom_offsets: list[int] = []
        self._highlighted_page_index: int | None = None
        self._bookmark_item_by_page = {}
        self._bookmark_pages_sorted = []
        self._is_text_selection_mode = True
        self._is_pdf_edit_mode = False
        self._single_page_view_enabled = False
        self._thumbnails_on_left = False
        self._mouse_mode_indicator = QToolButton()
        self._persistence = DesktopPersistence(
            preferences_path=_PANE_SETTINGS_PATH,
            passwords_path=_DOCUMENT_PASSWORDS_PATH,
        )
        self._file_renamer = DocumentFileRenamer()
        self._is_restoring_pane_visibility = False
        self._thread_pool = QThreadPool.globalInstance()

    def _new_document_reader(self) -> PdfDocument:
        """Return one document reader configured with the OCR backend."""
        return PdfDocument(ocr_backend=self._ocr_backend)

    def _configure_window_shell(self) -> None:
        """Configure the top-level window frame."""
        self.setWindowTitle("Open PDF")
        self.resize(1100, 800)

    def _render_device_pixel_ratio(self) -> float:
        """Return the screen scale used for PDF rasterization."""
        screen = self.screen()
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return 1.0

        return max(screen.devicePixelRatio(), 1.0)

    def _build_document_view(self) -> None:
        """Build the central scrolling page surface."""
        self._empty_state_label = QLabel("Open a PDF to begin.")
        self._empty_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_state_label.setMinimumSize(640, 480)

        self._document_container = QWidget()
        self._document_layout = QVBoxLayout()
        self._document_layout.setContentsMargins(24, 24, 24, 24)
        self._document_layout.setSpacing(20)
        self._document_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._document_container.setLayout(self._document_layout)
        self._document_layout.addWidget(
            self._empty_state_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        self._document_scroll_area = QScrollArea()
        self._document_scroll_area.setWidget(self._document_container)
        self._document_scroll_area.setWidgetResizable(True)
        self._document_scroll_area.viewport().setFocusPolicy(
            Qt.FocusPolicy.StrongFocus,
        )
        self._document_scroll_area.viewport().installEventFilter(self)
        self._document_scroll_area.verticalScrollBar().valueChanged.connect(
            self._handle_document_scrolled,
        )

    def _build_side_panes(self) -> None:
        """Build the page thumbnails and bookmarks panes."""
        self._move_page_up_button = self._build_page_move_button(
            QStyle.StandardPixmap.SP_ArrowUp,
            "Move page up",
            self._move_current_page_up,
        )
        self._move_page_down_button = self._build_page_move_button(
            QStyle.StandardPixmap.SP_ArrowDown,
            "Move page down",
            self._move_current_page_down,
        )
        thumbnail_button_row = QWidget()
        thumbnail_button_layout = QHBoxLayout()
        thumbnail_button_layout.setContentsMargins(0, 0, 0, 0)
        thumbnail_button_layout.setSpacing(4)
        thumbnail_button_layout.addWidget(self._move_page_up_button)
        thumbnail_button_layout.addWidget(self._move_page_down_button)
        thumbnail_button_layout.addStretch()
        thumbnail_button_row.setLayout(thumbnail_button_layout)

        self._thumbnail_list = QListWidget()
        self._thumbnail_list.setFrameShape(QFrame.Shape.NoFrame)
        # The default windows11 scrollbar collapses to a hairline inside
        # its reserved gutter, which reads as dead padding next to the
        # thumbnails. Style it slim with an always-visible handle instead.
        self._thumbnail_list.setStyleSheet(
            """
            QListWidget QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 0;
            }
            QListWidget QScrollBar::handle:vertical {
                background: rgba(128, 128, 128, 140);
                border-radius: 5px;
                min-height: 24px;
            }
            QListWidget QScrollBar::handle:vertical:hover {
                background: rgba(160, 160, 160, 200);
            }
            QListWidget QScrollBar::add-line:vertical,
            QListWidget QScrollBar::sub-line:vertical {
                height: 0;
            }
            QListWidget QScrollBar::add-page:vertical,
            QListWidget QScrollBar::sub-page:vertical {
                background: transparent;
            }
            """,
        )
        thumbnail_pane_width = (
            self._thumbnail_item_size().width()
            + self._thumbnail_list.verticalScrollBar().sizeHint().width()
        )
        self._thumbnail_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        # Keep the scrollbar gutter reserved: icons scale with viewport
        # width, so a scrollbar that comes and goes would oscillate the
        # icon size (and recurse through the resize event filter).
        self._thumbnail_list.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn,
        )
        self._thumbnail_list.setViewMode(QListView.ViewMode.IconMode)
        self._thumbnail_list.setFlow(QListView.Flow.TopToBottom)
        self._thumbnail_list.setWrapping(False)
        self._thumbnail_list.setMovement(QListView.Movement.Static)
        self._thumbnail_list.setResizeMode(QListView.ResizeMode.Adjust)
        self._thumbnail_list.setSpacing(8)
        self._thumbnail_list.setIconSize(self._thumbnail_icon_size())
        self._update_thumbnail_grid_size()
        self._thumbnail_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu,
        )
        self._thumbnail_list.currentRowChanged.connect(
            self._handle_thumbnail_selected,
        )
        self._thumbnail_list.customContextMenuRequested.connect(
            self._show_thumbnail_context_menu,
        )
        self._thumbnail_list.verticalScrollBar().valueChanged.connect(
            self._handle_thumbnail_list_scrolled,
        )
        self._thumbnail_list.viewport().installEventFilter(self)

        # Declared as QWidget because _ViewPaneHost exposes it as a mutable
        # (therefore invariant) QWidget member; nothing here needs the
        # _PreferredWidthPane subclass API beyond its sizeHint override.
        self._thumbnail_pane: QWidget = _PreferredWidthPane(
            thumbnail_pane_width,
        )
        self._thumbnail_pane.setMinimumWidth(thumbnail_pane_width)
        thumbnail_layout = QVBoxLayout()
        thumbnail_layout.setContentsMargins(0, 0, 0, 0)
        thumbnail_layout.setSpacing(4)
        thumbnail_layout.addWidget(thumbnail_button_row)
        thumbnail_layout.addWidget(self._thumbnail_list)
        self._thumbnail_pane.setLayout(thumbnail_layout)

        self._bookmark_tree = QTreeWidget()
        self._bookmark_tree.setHeaderHidden(True)
        self._bookmark_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu,
        )
        self._bookmark_tree.itemActivated.connect(
            self._handle_bookmark_selected,
        )
        self._bookmark_tree.itemClicked.connect(self._handle_bookmark_selected)
        self._bookmark_tree.customContextMenuRequested.connect(
            self._show_bookmark_context_menu,
        )

    def _build_content_splitter(self) -> QSplitter:
        """Build the document view and extracted-text content pane.

        Returns:
            The splitter that contains the document view and text panel.

        """
        self._page_text = QTextEdit()
        self._page_text.setReadOnly(True)
        self._page_text.setMinimumHeight(180)
        self._page_text.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu,
        )
        self._page_text.customContextMenuRequested.connect(
            self._show_page_text_context_menu,
        )
        self._page_text.setPlaceholderText(
            "Extracted text for the current page appears here.",
        )
        self._apply_text_selection_mode()

        self._notes_text = QTextEdit()
        self._notes_text.setAcceptRichText(False)
        self._notes_text.setMinimumHeight(180)
        self._notes_text.setPlaceholderText(
            "Plain-text document notes are stored inside this PDF.",
        )
        self._notes_text.textChanged.connect(self._handle_notes_changed)

        content_splitter = QSplitter(Qt.Orientation.Vertical)
        content_splitter.addWidget(self._document_scroll_area)
        content_splitter.addWidget(self._page_text)
        content_splitter.addWidget(self._notes_text)
        content_splitter.setStretchFactor(0, 4)
        content_splitter.setStretchFactor(1, 1)
        content_splitter.setStretchFactor(2, 1)

        return content_splitter

    def _build_central_splitter(
        self,
        *,
        content_splitter: QSplitter,
    ) -> None:
        """Attach the side panes and document view to the window."""
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self._bookmark_tree)
        main_splitter.addWidget(content_splitter)
        main_splitter.addWidget(self._thumbnail_pane)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)
        self._main_splitter = main_splitter
        self.setCentralWidget(main_splitter)

    def _build_page_move_button(
        self,
        icon: QStyle.StandardPixmap,
        tooltip: str,
        handler: object,
    ) -> QToolButton:
        """Build one thumbnail-pane page move button."""
        button = QToolButton()
        button.setIcon(self.style().standardIcon(icon))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.clicked.connect(handler)
        return button

    def _build_page_controls(self) -> None:
        """Build the page selector and search input controls."""
        self._page_selector = QSpinBox()
        self._page_selector.setMinimum(1)
        self._page_selector.setMaximum(1)
        self._page_selector.valueChanged.connect(self._handle_page_selected)

        self._search_input = QLineEdit()
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setPlaceholderText("Search text")
        self._search_input.installEventFilter(self)
        self._search_input.textChanged.connect(
            self._handle_search_text_changed,
        )
        self._search_input.returnPressed.connect(self._run_search)

        self._mouse_mode_indicator.setAutoRaise(True)
        self._mouse_mode_indicator.setToolTip("Click to toggle mouse mode")
        self._mouse_mode_indicator.clicked.connect(self._toggle_mouse_mode)
        self._update_mouse_mode_indicator()

    def _build_toolbar(self) -> None:
        """Build the tool bar and its action groups."""
        build_toolbar(self)

    def _handle_notes_changed(self) -> None:
        """Store edited notes in the active in-memory PDF document."""
        if self._sync.notes_text or not self._document.has_document():
            return

        try:
            changed = self._document.update_notes(
                self._notes_text.toPlainText(),
            )
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to update PDF notes:\n{error}")
            return

        if changed:
            self._refresh_actions()

    def _build_menu_bar(self) -> None:
        """Build the top-level menu bar."""
        build_menu_bar(self)

    def _choose_pdf(self) -> None:
        chosen_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF",
            str(Path.home()),
            "PDF Files (*.pdf)",
        )
        if not chosen_path:
            return

        self._open_path_in_tab(Path(chosen_path))

    def _open_document(self, path: Path) -> bool:
        if not self._confirm_unsaved_changes():
            return False

        remembered_password = self._recall_document_password(path)
        password = remembered_password
        try:
            while True:
                try:
                    self._document.open_document_with_password(
                        path,
                        password=password,
                    )
                    break
                except IncorrectPasswordError:
                    if password is not None:
                        self._forget_document_password(path)
                    password = self._prompt_for_document_password(
                        path=path,
                        invalid_password=True,
                    )
                    if password is None:
                        return False
                except PasswordRequiredError:
                    password = self._prompt_for_document_password(
                        path=path,
                        invalid_password=password is not None,
                    )
                    if password is None:
                        return False
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to open PDF:\n{error}")
            return False

        if password:
            self._remember_document_password(
                path=path,
                password=password,
            )

        self._load_cached_ocr_results(path)
        self._clear_search_results()
        self._populate_bookmarks()
        self._populate_thumbnails()
        self._refresh_document_view(scroll_to_page=True)
        logger.info(
            "Opened PDF with %d pages.",
            self._document.state.page_count,
        )
        return True

    def _load_cached_ocr_results(self, path: Path) -> None:
        """Seed the active document with any cached OCR output for `path`."""
        self._document.replace_ocr_results(self._ocr_cache.load_results(path))

    def _persist_document_ocr_cache(self) -> None:
        """Persist all OCR results for the active document when possible."""
        source_path = self._document.source_path
        if source_path is None:
            return

        self._ocr_cache.save_results(source_path, self._document.ocr_results())

    def _prompt_for_document_password(
        self,
        *,
        path: Path,
        invalid_password: bool,
    ) -> str | None:
        """Prompt for a PDF password, returning None when cancelled."""
        prompt = f"Enter the password for {path.name}:"
        if invalid_password:
            prompt = (
                f"Incorrect password.\n\nEnter the password for {path.name}:"
            )

        password, accepted = QInputDialog.getText(
            self,
            "Password Required",
            prompt,
            QLineEdit.EchoMode.Password,
        )
        if not accepted:
            return None

        return password

    def _show_previous_page(self) -> None:
        self._document.previous_page()
        self._sync_current_page_ui(scroll_to_page=True)

    def _show_next_page(self) -> None:
        self._document.next_page()
        self._sync_current_page_ui(scroll_to_page=True)

    def _set_single_page_view_enabled(self, *, enabled: bool) -> None:
        if self._single_page_view_enabled == enabled:
            return

        self._single_page_view_enabled = enabled
        if self._document.has_document():
            self._refresh_document_view(scroll_to_page=True)
        self._refresh_actions()

    def _rotate_current_page(self) -> None:
        try:
            self._document.rotate_clockwise()
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to rotate page:\n{error}")
            return

        self._populate_thumbnails()
        self._refresh_document_view(scroll_to_page=True)

    def _move_current_page_up(self) -> None:
        self._move_current_page_by(-1)

    def _move_current_page_down(self) -> None:
        self._move_current_page_by(1)

    def _move_current_page_by(self, offset: int) -> None:
        page_index = self._document.state.current_page_index
        destination_index = page_index + offset
        if not 0 <= destination_index < self._document.state.page_count:
            return

        try:
            self._document.move_page(page_index, destination_index)
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to move page:\n{error}")
            return

        self._clear_search_results()
        self._populate_bookmarks()
        self._populate_thumbnails()
        self._refresh_document_view(scroll_to_page=True)

    def _insert_blank_page_before(self) -> None:
        """Insert a blank page ahead of the current page."""
        self._insert_blank_page_at(self._document.state.current_page_index)

    def _insert_blank_page_after(self) -> None:
        """Insert a blank page behind the current page."""
        self._insert_blank_page_at(self._document.state.current_page_index + 1)

    def _insert_blank_page_at(self, at_index: int) -> None:
        if not self._document.has_document():
            return

        try:
            self._document.insert_blank_page(at_index=at_index)
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to insert page:\n{error}")
            return

        self._clear_search_results()
        self._populate_bookmarks()
        self._populate_thumbnails()
        self._refresh_document_view(scroll_to_page=True)
        self._refresh_actions()
        self.statusBar().showMessage("Inserted a blank page.", 5000)

    def _release_background_render_handles(self) -> None:
        """Close cached render handles so on-disk file swaps can proceed.

        Waits for in-flight background renders first; skips the close when
        the pool does not drain in time so no handle is closed mid-render.
        """
        wait_for_done = getattr(self._thread_pool, "waitForDone", None)
        if wait_for_done is None or wait_for_done(
            _RENDER_HANDLE_RELEASE_TIMEOUT_MS,
        ):
            RENDER_HANDLE_CACHE.close_all()

    def _save(self) -> None:
        if not self._document.has_document():
            return

        source_path = self._document.source_path
        if source_path is None:
            return

        self._release_background_render_handles()
        try:
            self._document.save()
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to save PDF:\n{error}")
            return

        self._refresh_actions()
        self._update_status_bar()
        self._persist_document_ocr_cache()
        self.statusBar().showMessage(f"Saved {source_path}", 5000)
        logger.info("Saved PDF.")

    def _save_as(self) -> None:
        if not self._document.has_document():
            return

        source_path = self._document.source_path
        default_path = source_path or (Path.home() / "document.pdf")

        chosen_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save As",
            str(default_path),
            "PDF Files (*.pdf)",
        )
        if not chosen_path:
            return

        target_path = Path(chosen_path)
        if source_path is not None and self._normalize_document_path(
            target_path,
        ) == self._normalize_document_path(source_path):
            self._save()
            return

        try:
            self._document.save_as(target_path)
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to save PDF as:\n{error}")
            return

        self._refresh_actions()
        self._update_status_bar()
        self._persist_document_ocr_cache()
        self.statusBar().showMessage(f"Saved as {chosen_path}", 5000)
        logger.info("Saved PDF as a new file.")

    def _edit_document_properties(self) -> None:
        """Prompt for and update the active PDF's editable metadata."""
        if not self._document.has_document():
            return

        current_metadata = self._document.metadata()
        updated_properties = self._prompt_for_document_properties(
            current_info_dict=current_metadata.info_dict,
            current_custom_info_dict=current_metadata.custom_info_dict,
            current_xmp_xml=current_metadata.xmp_xml,
        )
        if updated_properties is None:
            return

        updated_info_dict, updated_custom_info, updated_xmp_xml = (
            updated_properties
        )
        try:
            self._document.update_metadata(
                info_dict=updated_info_dict,
                custom_info_dict=updated_custom_info,
                xmp_xml=updated_xmp_xml,
            )
        except PDF_IO_ERRORS as error:
            self._show_error(f"Failed to update PDF properties:\n{error}")
            return

        self._refresh_actions()
        self._update_status_bar()
        self.statusBar().showMessage("Updated PDF properties", 5000)

    def _prompt_for_document_properties(
        self,
        *,
        current_info_dict: dict[str, str],
        current_custom_info_dict: dict[str, str],
        current_xmp_xml: str,
    ) -> DocumentPropertyValues | None:
        """Prompt for editable standard, custom, and XMP metadata."""
        return prompt_document_properties(
            current_info_dict=current_info_dict,
            current_custom_info_dict=current_custom_info_dict,
            current_xmp_xml=current_xmp_xml,
            parent=self,
        )

    def _confirm_unsaved_changes(self) -> bool:
        if not self._document.is_dirty():
            return True

        response = QMessageBox.question(
            self,
            "Unsaved Changes",
            "Save changes to the current PDF before continuing?",
            (
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel
            ),
            QMessageBox.StandardButton.Save,
        )
        if response == QMessageBox.StandardButton.Cancel:
            return False

        if response == QMessageBox.StandardButton.Save:
            if self._document.can_save():
                self._save()
            else:
                self._save_as()
            return not self._document.is_dirty()

        return True

    def _handle_page_selected(self, page_number: int) -> None:
        if self._sync.page_selector or not self._document.has_document():
            return

        self._document.go_to_page(page_number - 1)
        self._sync_current_page_ui(scroll_to_page=True)

    def _focus_search_input(self) -> None:
        if not self._document.has_document():
            return

        self._search_bar.show()
        self._search_debounce_timer.stop()
        self._update_search_bar_state()
        self._search_input.setFocus()
        self._search_input.selectAll()

    def _hide_search_bar(self) -> None:
        self._search_debounce_timer.stop()
        if self._search_input.text() or self._search.matches:
            self._search_input.clear()
            self._clear_search_results()
            if self._document.has_document():
                self._refresh_document_view(scroll_to_page=False)

        self._search_bar.hide()
        self._update_search_bar_state()
        self._refresh_actions()

    def _handle_search_text_changed(self, text: str) -> None:
        if self._search_bar.isHidden() or not self._document.has_document():
            return

        if not text.strip():
            self._search_debounce_timer.stop()
            self._run_search()
            return

        self._search_debounce_timer.start()

    def _update_search_bar_state(self) -> None:
        query = self._search_input.text().strip()
        if self._search_bar.isHidden() or not query:
            self._search_status_label.clear()
            return

        if query != self._search.last_query:
            self._search_status_label.clear()
            return

        if self._search.matches and self._search.match_index >= 0:
            self._search_status_label.setText(
                f"{self._search.match_index + 1}/{len(self._search.matches)}",
            )
            return

        self._search_status_label.setText("No results")

    def _go_back_history(self) -> None:
        self._record_history_scroll_position()
        self._restore_history_scroll_state(self._document.go_back_history())

    def _go_forward_history(self) -> None:
        self._record_history_scroll_position()
        self._restore_history_scroll_state(self._document.go_forward_history())

    def _refresh_actions(self) -> None:
        has_document = self._document.has_document()
        ocr_enabled = (
            has_document
            and not self._document.is_dirty()
            and not self._ocr.active
        )
        self._save_action.setEnabled(self._document.can_save())
        self._save_as_action.setEnabled(has_document)
        self._run_ocr_page_action.setEnabled(ocr_enabled)
        self._run_ocr_document_action.setEnabled(ocr_enabled)
        self._rename_file_action.setEnabled(has_document)
        self._print_action.setEnabled(has_document)
        self._properties_action.setEnabled(has_document)
        self._close_tab_action.setEnabled(
            has_document or len(self._tab_sessions) > 1,
        )
        self._history_back_shortcut_action.setEnabled(
            self._document.can_go_back_history(),
        )
        self._history_forward_shortcut_action.setEnabled(
            self._document.can_go_forward_history(),
        )
        self._previous_page_shortcut_action.setEnabled(has_document)
        self._next_page_shortcut_action.setEnabled(has_document)
        self._zoom_in_shortcut_action.setEnabled(has_document)
        self._zoom_out_shortcut_action.setEnabled(has_document)
        self._actual_size_action.setEnabled(has_document)
        self._fit_width_action.setEnabled(has_document)
        self._fit_page_action.setEnabled(has_document)
        self._single_page_view_action.setEnabled(has_document)
        self._rotate_right_action.setEnabled(has_document)
        self._page_selector.setEnabled(has_document)
        page_index = self._document.state.current_page_index
        self._move_page_up_button.setEnabled(has_document and page_index > 0)
        self._move_page_down_button.setEnabled(
            has_document and page_index < self._document.state.page_count - 1,
        )
        has_search_matches = bool(self._search.matches)
        self._find_action.setEnabled(has_document)
        self._previous_match_action.setEnabled(has_search_matches)
        self._next_match_action.setEnabled(has_search_matches)
        self._edit_pdf_action.setEnabled(has_document)
        self._remove_selected_text_action.setEnabled(has_document)
        if not has_document:
            self._search_bar.hide()
        self._update_search_bar_state()
        self._sync_active_tab_caption()

    def _update_status_bar(self) -> None:
        state = self._document.state
        search_status = ""
        if self._search.matches and self._search.match_index >= 0:
            search_status = (
                f" | Match {self._search.match_index + 1} / "
                f"{len(self._search.matches)}"
            )

        ocr_status = ""
        if self._ocr.active:
            ocr_status = (
                f" | OCR {self._ocr.completed_pages} / {self._ocr.total_pages}"
            )

        self.statusBar().showMessage(
            f"{state.page_label()} | Zoom {state.zoom:.2f}x"
            f"{search_status}{ocr_status}",
        )

    def _show_error(self, message: str) -> None:
        logger.error("%s", message)
        QMessageBox.critical(self, "Open PDF", message)

    def _show_about_dialog(self) -> None:
        show_about_open_pdf_dialog(self)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Prompt before closing a window with unsaved PDF edits."""
        if not self._confirm_close_all_tabs():
            event.ignore()
            return

        for session in self._tab_sessions:
            session.document.close_document()
        super().closeEvent(event)

    def _confirm_close_all_tabs(self) -> bool:
        """Prompt through each tab before closing the entire window."""
        original_index = self._active_tab_index
        for index in range(len(self._tab_sessions)):
            self._activate_document_tab(index)
            if not self._confirm_unsaved_changes():
                if 0 <= original_index < len(self._tab_sessions):
                    self._activate_document_tab(original_index)
                return False

        if 0 <= original_index < len(self._tab_sessions):
            self._activate_document_tab(original_index)

        return True

    def eventFilter(  # noqa: N802
        self,
        watched: QObject,
        event: QEvent,
    ) -> bool:
        """Handle Ctrl+wheel zoom gestures for the document viewport.

        - Consumes wheel events only when the document viewport receives a
          Ctrl-modified wheel gesture.
        - Delegates all other events to the Qt base implementation.

        Returns:
            True when the zoom gesture is consumed by the viewport filter.

        """
        search_input = getattr(self, "_search_input", None)
        if (
            search_input is not None
            and watched is search_input
            and event.type() == QEvent.Type.KeyPress
        ):
            key_event = event if isinstance(event, QKeyEvent) else None
            if key_event is not None and key_event.key() == Qt.Key.Key_Escape:
                self._hide_search_bar()
                event.accept()
                return True

        document_scroll_area = getattr(self, "_document_scroll_area", None)
        if (
            document_scroll_area is not None
            and watched is document_scroll_area.viewport()
            and event.type() == QEvent.Type.KeyPress
            and self._single_page_view_enabled
        ):
            key_event = event if isinstance(event, QKeyEvent) else None
            if (
                key_event is not None
                and key_event.modifiers() == Qt.KeyboardModifier.NoModifier
                and key_event.key() in {Qt.Key.Key_Up, Qt.Key.Key_Down}
            ):
                if key_event.key() == Qt.Key.Key_Up:
                    self._show_previous_page()
                else:
                    self._show_next_page()
                key_event.accept()
                return True

        if (
            document_scroll_area is not None
            and watched is document_scroll_area.viewport()
            and event.type() == QEvent.Type.Wheel
        ):
            wheel_event = event if isinstance(event, QWheelEvent) else None
            if (
                wheel_event is not None
                and wheel_event.modifiers()
                & Qt.KeyboardModifier.ControlModifier
            ):
                target_zoom = self._ctrl_wheel_zoom_target(
                    angle_delta_y=wheel_event.angleDelta().y(),
                    pixel_delta_y=wheel_event.pixelDelta().y(),
                )
                if target_zoom is None:
                    return False

                self._apply_zoom_preview(
                    target_zoom,
                    anchor_position=wheel_event.position(),
                )
                wheel_event.accept()
                return True

        thumbnail_list = getattr(self, "_thumbnail_list", None)
        if (
            thumbnail_list is not None
            and watched is thumbnail_list.viewport()
            and event.type() in {QEvent.Type.Resize, QEvent.Type.Show}
        ):
            self._update_thumbnail_grid_size()
            # Newly exposed rows (pane shown, splitter/window resized, or
            # side-pane swapped) have no scroll signal; render them now.
            self._refresh_visible_thumbnails()

        return super().eventFilter(watched, event)
