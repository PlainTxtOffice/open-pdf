# ruff: noqa: E402

import json
import logging
import os
import sys

from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_FONT_DIRECTORY = Path(__file__).resolve().parents[1] / "assets" / "fonts"
if _FONT_DIRECTORY.exists():
    os.environ.setdefault("QT_QPA_FONTDIR", str(_FONT_DIRECTORY))
import pymupdf
import pytest

from PySide6.QtGui import QAction
from PySide6.QtGui import QCloseEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtGui import QWheelEvent
from PySide6.QtCore import QEvent
from PySide6.QtCore import QPoint
from PySide6.QtCore import QPointF
from PySide6.QtCore import QRectF
from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QAbstractPrintDialog
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QListView
from PySide6.QtWidgets import QMenu
from PySide6.QtWidgets import QSplitter
from PySide6.QtWidgets import QStyle
from PySide6.QtWidgets import QToolBar
from PySide6.QtWidgets import QToolButton

import open_pdf.gui.views.root_window.window as app_module
import open_pdf.gui.views.root_window.navigation.bookmarks as bookmarks_module
import open_pdf.gui.views.rendering.selection as selection_module
import open_pdf.gui.views.root_window.navigation.page_links as page_links_module
import open_pdf.gui.views.root_window.panes.thumbnails as thumbnails_module
import open_pdf.gui.views.workflows.printing as printing_module
from open_pdf.adapters.ocr.cache import OcrCache
from open_pdf.domains.document.models import PdfOcrPageResult, PdfPageLink
from open_pdf.gui.app import MainWindow
from open_pdf.gui.views.rendering.page_metrics import PAGE_CONTENT_CHROME
from open_pdf.gui.views.rendering.page_surface import PageSurfaceLabel
from open_pdf.gui.views.dialogs.properties_dialog import DocumentPropertiesDialog


class _NoOpThreadPool:
    def start(self, _task: object) -> None:
        return None


class _ImmediateThreadPool:
    def start(self, task: object) -> None:
        task.run()


class _FailingThreadPool:
    def start(self, _task: object) -> None:
        msg = "Dirty documents should not queue source-file render tasks."
        raise AssertionError(msg)


class _CollectingThreadPool:
    def __init__(self) -> None:
        self.tasks: list[object] = []

    def start(self, task: object) -> None:
        self.tasks.append(task)


class _FakeContextMenu:
    def __init__(self, *_args, **_kwargs) -> None:
        self._actions: list[QAction] = []

    def addAction(self, text: str) -> QAction:
        action = QAction(text)
        self._actions.append(action)
        return action

    def actions(self) -> list[QAction]:
        return self._actions

    def exec(self, *_args, **_kwargs) -> QAction | None:
        return self._actions[0] if self._actions else None

    def setPalette(self, _palette: object) -> None:
        return None

    def setStyleSheet(self, _style_sheet: str) -> None:
        return None


@pytest.fixture(autouse=True)
def _isolate_ui_settings(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        app_module,
        "_PANE_SETTINGS_PATH",
        tmp_path / "ui-state.json",
    )


def _app() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


def _create_sample_pdf(path: Path) -> None:
    document = pymupdf.open()
    try:
        first_page = document.new_page()
        first_page.insert_text((72, 72), "first page")

        second_page = document.new_page()
        second_page.insert_text((72, 72), "second page")

        document.save(path)
    finally:
        document.close()


def _create_three_page_pdf(path: Path) -> None:
    document = pymupdf.open()
    try:
        for page_number in range(1, 4):
            page = document.new_page()
            page.insert_text((72, 72), f"page {page_number}")

        document.save(path)
    finally:
        document.close()


def _create_single_page_pdf(
    path: Path,
    *,
    width: float,
    height: float,
) -> None:
    document = pymupdf.open()
    try:
        page = document.new_page(width=width, height=height)
        page.insert_text((20, 40), "single page")
        document.save(path)
    finally:
        document.close()


def _create_password_protected_pdf(path: Path) -> None:
    document = pymupdf.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), "locked")
        document.save(
            path,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner-pass",
            user_pw="user-pass",
        )
    finally:
        document.close()


def _create_image_only_pdf(path: Path, *, page_count: int = 1) -> None:
    document = pymupdf.open()
    try:
        for _ in range(page_count):
            document.new_page()
        document.save(path)
    finally:
        document.close()


def _create_linked_pdf(path: Path) -> None:
    document = pymupdf.open()
    try:
        document.new_page()
        document.new_page()
        document.new_page()
        document.new_page()

        page_one = document.load_page(0)
        page_two = document.load_page(1)
        page_two.insert_text((72, 72), "target page")

        page_one.insert_text((72, 72), "external link")
        page_one.insert_link(
            {
                "kind": pymupdf.LINK_URI,
                "from": pymupdf.Rect(72, 72, 152, 96),
                "uri": "https://example.com/spec",
            },
        )
        page_one.insert_text((72, 140), "internal link")
        page_one.insert_link(
            {
                "kind": pymupdf.LINK_GOTO,
                "from": pymupdf.Rect(72, 140, 152, 164),
                "page": 1,
                "to": pymupdf.Point(20, 250),
            },
        )

        document.save(path)
    finally:
        document.close()


def _build_ocr_page_result(page_index: int, text: str) -> PdfOcrPageResult:
    words = []
    cursor_x = 72.0
    for word_index, word in enumerate(text.split()):
        word_width = max(len(word) * 8.0, 12.0)
        words.append(
            (
                cursor_x,
                72.0,
                cursor_x + word_width,
                92.0,
                word,
                0,
                0,
                word_index,
            ),
        )
        cursor_x += word_width + 8.0

    return PdfOcrPageResult(
        page_index=page_index,
        text=text,
        words=tuple(words),
        engine_name="fake-ocr",
    )


class _FakeOcrBackend:
    def __init__(self, results_by_page: dict[int, PdfOcrPageResult]) -> None:
        self._results_by_page = results_by_page
        self.calls: list[tuple[int, tuple[str, ...]]] = []

    def recognize_page(
        self,
        document: pymupdf.Document,
        page_index: int,
        *,
        language_codes: tuple[str, ...],
    ) -> PdfOcrPageResult:
        del document
        self.calls.append((page_index, language_codes))
        return self._results_by_page[page_index]


def _mouse_press_event(*, x: float, y: float) -> QMouseEvent:
    position = QPointF(x, y)
    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        position,
        position,
        position,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _ctrl_wheel_event(
    *,
    x: float,
    y: float,
    angle_delta_y: int,
    pixel_delta_y: int = 0,
) -> QWheelEvent:
    position = QPointF(x, y)
    return QWheelEvent(
        position,
        position,
        QPoint(0, pixel_delta_y),
        QPoint(0, angle_delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )


def test_thumbnail_items_do_not_show_page_captions() -> None:
    assert MainWindow._thumbnail_item_text(0) == ""


def test_open_document_logs_page_count(tmp_path: Path, caplog) -> None:
    _app()
    source_path = tmp_path / "logging.pdf"
    _create_sample_pdf(source_path)
    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()

    with caplog.at_level(logging.INFO, logger=app_module.__name__):
        assert window._open_document(source_path) is True

    assert "Opened PDF with 2 pages." in caplog.messages


def test_thumbnail_list_centers_icons_in_single_column() -> None:
    _app()
    window = MainWindow()
    thumbnail_list = window._thumbnail_list

    assert thumbnail_list.viewMode() == QListView.ViewMode.IconMode
    assert thumbnail_list.flow() == QListView.Flow.TopToBottom
    assert thumbnail_list.isWrapping() is False
    assert thumbnail_list.movement() == QListView.Movement.Static
    assert thumbnail_list.spacing() == 8
    assert (
        thumbnail_list.gridSize().width()
        >= window._thumbnail_item_size().width()
    )
    assert (
        thumbnail_list.gridSize().height()
        == window._thumbnail_item_size().height()
    )


def test_thumbnail_grid_uses_the_full_viewport_width() -> None:
    app = _app()
    window = MainWindow()
    window.resize(1000, 700)
    window.show()
    app.processEvents()

    window._update_thumbnail_grid_size()

    assert window._thumbnail_list.gridSize().width() == (
        window._thumbnail_list.viewport().width()
    )


def test_thumbnail_items_fill_the_viewport_width(tmp_path: Path) -> None:
    app = _app()
    source_path = tmp_path / "thumbnail-item-width.pdf"
    _create_sample_pdf(source_path)
    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.resize(1000, 700)
    window.show()
    window._open_document(source_path)
    app.processEvents()

    item = window._thumbnail_list.item(0)

    assert item is not None
    assert window._thumbnail_list.visualItemRect(item).width() == (
        window._thumbnail_list.viewport().width()
    )
    assert window._thumbnail_pane.width() == window._thumbnail_list.width()


def test_thumbnail_items_reserve_space_before_icons_render(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "thumbnail-spacing.pdf"
    _create_three_page_pdf(source_path)
    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()

    window.open_document_in_tab(source_path)

    expected_height = window._thumbnail_item_size().height()
    assert expected_height > window._thumbnail_icon_size().height()
    assert all(
        window._thumbnail_list.item(row).sizeHint().height() == expected_height
        for row in range(window._thumbnail_list.count())
    )


def test_thumbnail_pane_width_is_resizable_via_the_splitter() -> None:
    app = _app()
    window = MainWindow()
    window.resize(1100, 700)
    window.show()
    app.processEvents()

    splitter = window._main_splitter
    sizes = splitter.sizes()
    target = sizes[2] + 80
    splitter.setSizes([sizes[0], sizes[1] - 80, target])
    app.processEvents()

    assert abs(window._thumbnail_pane.width() - target) <= 1


def _widen_thumbnail_pane(window: MainWindow, extra_width: int) -> None:
    splitter = window._main_splitter
    sizes = splitter.sizes()
    splitter.setSizes(
        [sizes[0], sizes[1] - extra_width, sizes[2] + extra_width],
    )


def test_thumbnail_icons_scale_to_fill_a_wider_pane() -> None:
    app = _app()
    window = MainWindow()
    window.resize(1100, 700)
    window.show()
    app.processEvents()

    _widen_thumbnail_pane(window, 100)
    app.processEvents()

    viewport_width = window._thumbnail_list.viewport().width()
    icon_size = window._thumbnail_list.iconSize()
    assert icon_size.width() >= viewport_width - 16
    assert window._thumbnail_list.gridSize().width() == viewport_width
    assert window._thumbnail_list.gridSize().height() == (
        icon_size.height() + window._thumbnail_cell_padding().height()
    )


def test_growing_thumbnail_icons_queues_a_sharper_rerender(
    tmp_path: Path,
) -> None:
    app = _app()
    source_path = tmp_path / "thumbnail-rerender.pdf"
    _create_sample_pdf(source_path)
    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.open_document_in_tab(source_path)
    window.resize(1100, 700)
    window.show()
    app.processEvents()
    window._thumbnail_rendered_pages.add(0)

    _widen_thumbnail_pane(window, 100)
    app.processEvents()

    assert window._thumbnail_rerender_timer.isActive()

    generation_before = window._generations.thumbnail
    window._rerender_thumbnails()

    assert window._generations.thumbnail == generation_before + 1
    assert window._thumbnail_rendered_pages == set()
    assert window._thumbnail_render_max_dimension() == 2 * max(
        window._thumbnail_list.iconSize().width(),
        window._thumbnail_list.iconSize().height(),
    )


def test_thumbnail_icon_box_matches_the_document_page_aspect(
    tmp_path: Path,
) -> None:
    app = _app()
    source_path = tmp_path / "tall-pages.pdf"
    document = pymupdf.open()
    try:
        for _ in range(2):
            document.new_page(width=400, height=800)
        document.save(source_path)
    finally:
        document.close()

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.open_document_in_tab(source_path)
    window.resize(1100, 700)
    window.show()
    app.processEvents()

    icon_size = window._thumbnail_list.iconSize()
    viewport_width = window._thumbnail_list.viewport().width()
    assert icon_size.width() >= viewport_width - 16
    assert abs(icon_size.height() - icon_size.width() * 2) <= 2


def test_thumbnail_cell_padding_derives_from_style_metrics() -> None:
    _app()
    window = MainWindow()
    thumbnail_list = window._thumbnail_list
    style = thumbnail_list.style()

    focus_margin = style.pixelMetric(
        QStyle.PixelMetric.PM_FocusFrameHMargin,
        None,
        thumbnail_list,
    )
    spacing = max(
        style.pixelMetric(
            QStyle.PixelMetric.PM_LayoutVerticalSpacing,
            None,
            thumbnail_list,
        ),
        0,
    )
    padding = window._thumbnail_cell_padding()

    assert padding.width() == 2 * (focus_margin + 1)
    assert padding.height() == 2 * (focus_margin + 1) + spacing


def test_thumbnail_list_uses_native_scrollbar_width() -> None:
    _app()
    window = MainWindow()

    assert window._thumbnail_list.frameWidth() == 0
    scrollbar = window._thumbnail_list.verticalScrollBar()
    assert scrollbar.sizeHint().width() == scrollbar.style().pixelMetric(
        QStyle.PixelMetric.PM_ScrollBarExtent, None, scrollbar,
    )


def test_thumbnail_cells_reserve_only_a_small_margin_around_icons() -> None:
    _app()
    window = MainWindow()

    icon_size = window._thumbnail_icon_size()
    item_size = window._thumbnail_item_size()

    assert item_size.width() - icon_size.width() <= 16
    assert item_size.height() - icon_size.height() <= 16


def test_thumbnails_render_above_display_resolution_for_hidpi(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "thumbnail-resolution.pdf"
    _create_sample_pdf(source_path)
    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.open_document_in_tab(source_path)

    window._render_dirty_thumbnail(0)

    icon_sizes = window._thumbnail_list.item(0).icon().availableSizes()
    assert icon_sizes
    rendered = icon_sizes[0]
    icon_size = window._thumbnail_icon_size()
    assert max(rendered.width(), rendered.height()) >= 2 * max(
        icon_size.width(),
        icon_size.height(),
    )


def test_flat_bookmarks_do_not_reserve_an_expander_gutter(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "flat-bookmarks.pdf"
    _create_sample_pdf(source_path)

    document = pymupdf.open(source_path)
    document.set_toc([[1, "Cover", 1], [1, "Copyright", 2]])
    document.saveIncr()
    document.close()

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    assert window._bookmark_tree.rootIsDecorated() is False


def test_nested_bookmarks_retain_an_expander_gutter(tmp_path: Path) -> None:
    _app()
    source_path = tmp_path / "nested-bookmarks.pdf"
    _create_sample_pdf(source_path)

    document = pymupdf.open(source_path)
    document.set_toc([[1, "Chapter", 1], [2, "Topic", 2]])
    document.saveIncr()
    document.close()

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    assert window._bookmark_tree.rootIsDecorated() is True
    assert window._bookmark_tree.topLevelItem(0).childCount() == 1


def test_page_text_overlay_uses_word_boxes_for_selection() -> None:
    _app()
    page_label = PageSurfaceLabel()
    page_label.setFixedSize(210, 110)
    page_label.set_page_text_words(
        [
            (10.0, 10.0, 30.0, 20.0, "Hello", 0, 0, 0),
            (35.0, 10.0, 55.0, 20.0, "world", 0, 0, 1),
        ],
        zoom=2.0,
    )
    page_label.set_text_selection_enabled(enabled=True)

    page_label.text_layer().select_word_range(0, 1)
    menu = page_label.text_layer().createStandardContextMenu()
    action_texts = [action.text() for action in menu.actions()]

    assert page_label.selected_text() == "Hello world"
    assert page_label.text_layer().contextMenuPolicy() == (
        Qt.ContextMenuPolicy.CustomContextMenu
    )
    assert action_texts == ["Copy", "Select All"]
    assert menu.actions()[0].isEnabled() is True


def test_window_has_file_and_view_menus() -> None:
    _app()
    window = MainWindow()

    menu_titles = [action.text() for action in window.menuBar().actions()]

    assert menu_titles == ["File", "Edit", "View", "Help"]


def test_main_window_places_bookmarks_left_and_thumbnails_right() -> None:
    _app()
    window = MainWindow()

    main_splitter = window.centralWidget()

    assert isinstance(main_splitter, QSplitter)
    assert main_splitter.count() == 3
    assert main_splitter.widget(0) is window._bookmark_tree
    assert main_splitter.widget(2) is window._thumbnail_pane


def test_view_menu_can_swap_side_panes() -> None:
    _app()
    window = MainWindow()

    main_splitter = window.centralWidget()

    assert isinstance(main_splitter, QSplitter)

    window._thumbnails_left_side_action.trigger()

    assert main_splitter.widget(0) is window._thumbnail_pane
    assert main_splitter.widget(2) is window._bookmark_tree
    assert window._thumbnails_on_left is True
    assert window._thumbnails_left_side_action.isChecked() is True
    assert window._bookmarks_left_side_action.isChecked() is False

    window._bookmarks_left_side_action.trigger()

    assert main_splitter.widget(0) is window._bookmark_tree
    assert main_splitter.widget(2) is window._thumbnail_pane
    assert window._thumbnails_on_left is False


def test_file_menu_has_exit_and_help_menu_has_about(monkeypatch) -> None:
    _app()
    window = MainWindow()

    about_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        QMessageBox,
        "about",
        staticmethod(
            lambda _parent, title, text: about_calls.append((title, text)),
        ),
    )

    assert window._properties_action.text() == "Properties"
    assert window._rename_file_action.text() == "Rename File"
    assert window._run_ocr_page_action.text() == "Run OCR on Current Page"
    assert window._run_ocr_document_action.text() == "Run OCR on Document"
    assert window._print_action.text() == "Print"
    assert window._edit_pdf_action.text() == "Edit PDF"
    assert window._remove_selected_text_action.text() == "Remove Content"
    assert window._close_tab_action.text() == "Close Tab"
    assert window._close_tab_action.shortcut().toString() == "Ctrl+W"
    assert window._exit_action.text() == "Exit"

    menus = {
        menu.title(): menu for menu in window.menuBar().findChildren(QMenu)
    }
    file_menu = menus["File"]
    edit_menu = menus["Edit"]

    assert file_menu is not None
    assert edit_menu is not None
    assert [
        action.text()
        for action in file_menu.actions()
        if not action.isSeparator()
    ] == [
        "Open",
        "Save",
        "Save As",
        "Rename File",
        "Print",
        "Properties",
        "Close Tab",
        "Exit",
    ]
    assert [
        action.text()
        for action in edit_menu.actions()
        if not action.isSeparator()
    ] == [
        "Run OCR on Current Page",
        "Run OCR on Document",
        "Insert Blank Page Before",
        "Insert Blank Page After",
        "Remove Content",
    ]


def test_toolbar_shows_edit_pdf_text_button(monkeypatch) -> None:
    _app()
    about_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        MainWindow,
        "_show_about_dialog",
        lambda _window: about_calls.append(
            (
                "About Open PDF",
                "Open PDF\n\nA lightweight desktop PDF viewer and editor.",
            )
        ),
    )
    window = MainWindow()

    edit_pdf_button = window.findChild(QToolButton, "edit-pdf-button")

    assert edit_pdf_button is not None
    assert edit_pdf_button.defaultAction() is window._edit_pdf_action
    assert edit_pdf_button.toolButtonStyle() == (
        Qt.ToolButtonStyle.ToolButtonTextOnly
    )
    assert edit_pdf_button.text() == "Edit PDF"
    assert window._about_action.text() == "About Open PDF"

    window._about_action.trigger()

    assert about_calls == [
        (
            "About Open PDF",
            "Open PDF\n\nA lightweight desktop PDF viewer and editor.",
        ),
    ]


def test_file_menu_includes_print_action_and_triggers_handler(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "print.pdf"
    _create_sample_pdf(source_path)
    print_calls: list[bool] = []

    monkeypatch.setattr(
        MainWindow,
        "_print_document",
        lambda self: print_calls.append(self._document.has_document()),
    )

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()

    assert window._print_action.text() == "Print"
    assert window._print_action.isEnabled() is False

    window._open_document(source_path)

    assert window._print_action.isEnabled() is True

    window._print_action.trigger()

    assert print_calls == [True]


def test_ocr_page_action_updates_extracted_text_and_enables_actions(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "ocr-page.pdf"
    _create_image_only_pdf(source_path)
    backend = _FakeOcrBackend({0: _build_ocr_page_result(0, "scanned alpha")})
    cache = OcrCache(cache_dir=tmp_path / "ocr-cache")

    window = MainWindow(ocr_backend=backend, ocr_cache=cache)
    window._thread_pool = _ImmediateThreadPool()

    assert window._run_ocr_page_action.isEnabled() is False
    assert window._run_ocr_document_action.isEnabled() is False

    window._open_document(source_path)

    assert window._run_ocr_page_action.isEnabled() is True
    assert window._run_ocr_document_action.isEnabled() is True

    window._run_ocr_page_action.trigger()

    assert backend.calls == [(0, ())]
    assert window._page_text.toPlainText() == "scanned alpha"
    assert window._document.has_ocr_result(0) is True
    assert window._document.is_dirty() is False
    assert "OCR completed for 1 page." in window.statusBar().currentMessage()


def test_open_document_loads_cached_ocr_results_without_backend(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "ocr-cache.pdf"
    _create_image_only_pdf(source_path)
    cache = OcrCache(cache_dir=tmp_path / "ocr-cache")
    backend = _FakeOcrBackend({0: _build_ocr_page_result(0, "cached text")})

    first_window = MainWindow(ocr_backend=backend, ocr_cache=cache)
    first_window._thread_pool = _ImmediateThreadPool()
    first_window._open_document(source_path)
    first_window._run_ocr_page_action.trigger()

    assert backend.calls == [(0, ())]

    second_window = MainWindow(ocr_cache=cache)
    second_window._thread_pool = _NoOpThreadPool()
    second_window._open_document(source_path)

    assert second_window._document.has_ocr_result(0) is True
    assert second_window._document.page_text(0) == "cached text"
    assert second_window._page_text.toPlainText() == "cached text"


def test_ocr_action_shows_tesseract_setup_guidance_when_backend_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "ocr-guidance.pdf"
    _create_image_only_pdf(source_path)
    shown_errors: list[str] = []

    monkeypatch.setattr(
        MainWindow,
        "_show_error",
        lambda self, message: shown_errors.append(message),
    )

    window = MainWindow(
        ocr_unavailable_message=(
            "OCR is unavailable because Tesseract is not fully configured.\n\n"
            "- Install the optional Python OCR dependencies with "
            '"pip install -e .[ocr]".\n'
            "- Install Tesseract OCR and add tesseract.exe to PATH, or set "
            "TESSERACT_CMD to its full path."
        ),
    )
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    assert window._run_ocr_page_action.isEnabled() is True
    assert window._run_ocr_document_action.isEnabled() is True

    window._run_ocr_page_action.trigger()

    assert shown_errors == [
        "OCR is unavailable because Tesseract is not fully configured.\n\n"
        "- Install the optional Python OCR dependencies with "
        '"pip install -e .[ocr]".\n'
        "- Install Tesseract OCR and add tesseract.exe to PATH, or set "
        "TESSERACT_CMD to its full path.",
    ]


def test_print_document_honors_selected_page_range(
    monkeypatch, tmp_path: Path
) -> None:
    _app()
    source_path = tmp_path / "print-range.pdf"
    _create_three_page_pdf(source_path)

    dialog_state: dict[str, object] = {}
    printer_instances: list[object] = []
    painter_instances: list[object] = []
    rendered_pages: list[int] = []

    class _FakePrinter:
        class PrinterMode:
            HighResolution = object()

        class Unit:
            DevicePixel = object()

        def __init__(self, _mode: object) -> None:
            self.new_page_calls = 0
            printer_instances.append(self)

        def resolution(self) -> int:
            return 72

        def pageRect(self, _unit: object) -> QRectF:
            return QRectF(0, 0, 600, 800)

        def printRange(self) -> QAbstractPrintDialog.PrintRange:
            return QAbstractPrintDialog.PrintRange.PageRange

        def fromPage(self) -> int:
            return 2

        def toPage(self) -> int:
            return 2

        def newPage(self) -> bool:
            self.new_page_calls += 1
            return True

    class _FakePrintDialog:
        def __init__(self, printer: object, _parent: object) -> None:
            dialog_state["printer"] = printer
            dialog_state["options"] = []

        def setMinMax(self, min_page: int, max_page: int) -> None:
            dialog_state["min_max"] = (min_page, max_page)

        def setOption(
            self,
            option: QAbstractPrintDialog.PrintDialogOption,
            on: bool = True,
        ) -> None:
            options = dialog_state["options"]
            assert isinstance(options, list)
            options.append((option, on))

        def exec(self) -> int:
            return QDialog.DialogCode.Accepted

    class _FakeImage:
        def width(self) -> int:
            return 300

        def height(self) -> int:
            return 400

    class _FakePainter:
        def __init__(self) -> None:
            self.draw_calls: list[tuple[QRectF, object]] = []
            painter_instances.append(self)

        def begin(self, _printer: object) -> bool:
            return True

        def drawImage(self, target_rect: QRectF, image: object) -> None:
            self.draw_calls.append((target_rect, image))

        def end(self) -> None:
            return None

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    def _fake_render_page_at_zoom(page_index: int, *, zoom: float) -> object:
        assert zoom == 1.0
        rendered_pages.append(page_index)
        return object()

    monkeypatch.setattr(printing_module, "QPrinter", _FakePrinter)
    monkeypatch.setattr(printing_module, "QPrintDialog", _FakePrintDialog)
    monkeypatch.setattr(printing_module, "QPainter", _FakePainter)
    monkeypatch.setattr(
        printing_module,
        "qimage_from_pymupdf",
        lambda _pixmap: _FakeImage(),
    )
    monkeypatch.setattr(
        window._document,
        "render_page_at_zoom",
        _fake_render_page_at_zoom,
    )

    window._print_document()

    assert dialog_state["min_max"] == (1, 3)
    assert dialog_state["options"] == [
        (QAbstractPrintDialog.PrintDialogOption.PrintPageRange, True),
    ]
    assert rendered_pages == [1]
    assert len(painter_instances) == 1
    painter = painter_instances[0]
    assert isinstance(painter, _FakePainter)
    assert len(painter.draw_calls) == 1
    printer = printer_instances[0]
    assert isinstance(printer, _FakePrinter)
    assert printer.new_page_calls == 0


def test_open_document_shows_specific_message_for_password_protected_pdf(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "protected.pdf"
    _create_password_protected_pdf(source_path)

    shown_errors: list[str] = []
    prompt_calls: list[bool] = []
    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    monkeypatch.setattr(window, "_show_error", shown_errors.append)
    monkeypatch.setattr(
        window,
        "_prompt_for_document_password",
        lambda **kwargs: (
            prompt_calls.append(kwargs["invalid_password"]) or None
        ),
    )

    window._open_document(source_path)

    assert prompt_calls == [False]
    assert shown_errors == []
    assert window._document.has_document() is False


def test_open_document_prompts_for_password_and_retries_until_success(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "protected-open.pdf"
    _create_password_protected_pdf(source_path)

    prompt_calls: list[bool] = []
    shown_errors: list[str] = []
    entered_passwords = iter(["wrong-pass", "user-pass"])
    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    monkeypatch.setattr(window, "_show_error", shown_errors.append)
    monkeypatch.setattr(
        window,
        "_prompt_for_document_password",
        lambda **kwargs: (
            prompt_calls.append(kwargs["invalid_password"])
            or next(entered_passwords)
        ),
    )

    window._open_document(source_path)

    assert prompt_calls == [False, True]
    assert shown_errors == []
    assert window._document.has_document() is True
    assert window._document.source_path == source_path


def test_reopening_protected_pdf_reuses_remembered_password(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "protected-remember.pdf"
    _create_password_protected_pdf(source_path)

    first_window = MainWindow()
    first_window._thread_pool = _NoOpThreadPool()
    prompt_calls: list[bool] = []
    monkeypatch.setattr(
        first_window,
        "_prompt_for_document_password",
        lambda **kwargs: (
            prompt_calls.append(kwargs["invalid_password"]) or "user-pass"
        ),
    )

    first_window._open_document(source_path)

    assert prompt_calls == [False]

    second_window = MainWindow()
    second_window._thread_pool = _NoOpThreadPool()
    monkeypatch.setattr(
        second_window,
        "_prompt_for_document_password",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("Remembered password should avoid a second prompt."),
        ),
    )

    second_window._open_document(source_path)

    assert second_window._document.has_document() is True
    assert second_window._document.source_path == source_path


def test_invalid_remembered_password_is_forgotten_and_replaced(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "protected-replace.pdf"
    _create_password_protected_pdf(source_path)

    seed_window = MainWindow()
    seed_window._thread_pool = _NoOpThreadPool()
    seed_window._remember_document_password(
        path=source_path,
        password="wrong-pass",
    )

    prompt_calls: list[bool] = []
    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    monkeypatch.setattr(
        window,
        "_prompt_for_document_password",
        lambda **kwargs: (
            prompt_calls.append(kwargs["invalid_password"]) or "user-pass"
        ),
    )

    window._open_document(source_path)

    assert prompt_calls == [True]

    reopened_window = MainWindow()
    reopened_window._thread_pool = _NoOpThreadPool()
    monkeypatch.setattr(
        reopened_window,
        "_prompt_for_document_password",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError(
                "Updated remembered password should avoid prompting."
            ),
        ),
    )

    reopened_window._open_document(source_path)

    assert reopened_window._document.has_document() is True


def test_open_document_returns_when_password_prompt_is_cancelled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "protected-cancel.pdf"
    _create_password_protected_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    prompt_calls: list[bool] = []
    monkeypatch.setattr(
        window,
        "_prompt_for_document_password",
        lambda **kwargs: (
            prompt_calls.append(kwargs["invalid_password"]) or None
        ),
    )

    window._open_document(source_path)

    assert prompt_calls == [False]
    assert window._document.has_document() is False


def test_cancelling_password_prompt_closes_new_tab_and_restores_previous_tab(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    first_path = tmp_path / "first.pdf"
    protected_path = tmp_path / "protected.pdf"
    _create_sample_pdf(first_path)
    _create_password_protected_pdf(protected_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.open_document_in_tab(first_path)
    window._document.go_to_page(1)
    window._document.state.set_zoom(1.5)

    prompt_calls: list[bool] = []
    monkeypatch.setattr(
        window,
        "_prompt_for_document_password",
        lambda **kwargs: (
            prompt_calls.append(kwargs["invalid_password"]) or None
        ),
    )

    window.open_document_in_tab(protected_path)

    assert prompt_calls == [False]
    assert window._document_tabs.count() == 1
    assert window._document_tabs.currentIndex() == 0
    assert window._document.source_path == first_path
    assert window._document.state.current_page_index == 1
    assert window._document.state.zoom == 1.5


def test_clicking_pdf_uri_link_opens_external_browser(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "uri-link.pdf"
    _create_linked_pdf(source_path)

    opened_urls: list[str] = []
    window = MainWindow()
    window._thread_pool = _ImmediateThreadPool()
    monkeypatch.setattr(
        page_links_module.QDesktopServices,
        "openUrl",
        lambda url: opened_urls.append(url.toString()) or True,
    )

    window._open_document(source_path)
    page_label = window._page_labels[0]

    assert isinstance(page_label, PageSurfaceLabel)

    inset = PAGE_CONTENT_CHROME / 2
    page_label.mousePressEvent(
        _mouse_press_event(x=90 + inset, y=84 + inset),
    )

    assert opened_urls == ["https://example.com/spec"]
    assert window._document.state.current_page_index == 0


def test_clicking_internal_pdf_link_navigates_to_target_page(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "internal-link.pdf"
    _create_linked_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _ImmediateThreadPool()
    window.resize(900, 500)
    window.show()
    _app().processEvents()

    window._open_document(source_path)
    _app().processEvents()
    page_label = window._page_labels[0]

    assert isinstance(page_label, PageSurfaceLabel)
    assert window._document.state.current_page_index == 0

    QTest.mouseClick(
        page_label.text_layer(),
        Qt.MouseButton.LeftButton,
        pos=QPoint(90, 150),
    )
    _app().processEvents()

    inset = PAGE_CONTENT_CHROME / 2
    target_page_label = window._page_labels[1]
    target_content_y = target_page_label.y() + round(
        target_page_label.height() - inset - 250
    )
    scroll_value = window._document_scroll_area.verticalScrollBar().value()

    assert window._document.state.current_page_index == 1
    assert target_content_y - scroll_value == 40


def test_stale_page_render_skips_rasterization_and_keeps_new_pending(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "stale-render.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    collecting_pool = _CollectingThreadPool()
    window._thread_pool = collecting_pool
    window._open_document(source_path)

    page_render_tasks = [
        task for task in collecting_pool.tasks if hasattr(task, "_request")
    ]
    stale_task = next(
        task for task in page_render_tasks if task._request.page_index == 0
    )
    stale_generation = stale_task._request.generation

    window._build_page_placeholders()
    window._refresh_visible_pages()

    page_zero_task_count = sum(
        task._request.page_index == 0
        for task in collecting_pool.tasks
        if hasattr(task, "_request")
    )
    assert page_zero_task_count == 2
    assert any(
        task._request.page_index == 0
        and task._request.generation != stale_generation
        for task in collecting_pool.tasks
        if hasattr(task, "_request")
    )

    def _unexpected_render(*_args, **_kwargs):
        msg = "Stale page renders should be discarded before rasterization."
        raise AssertionError(msg)

    monkeypatch.setattr(
        "open_pdf.gui.views.rendering.page_rendering.render_page",
        _unexpected_render,
    )

    stale_task.run()
    _app().processEvents()

    window._queue_page_render(0)

    assert (
        sum(
            task._request.page_index == 0
            for task in collecting_pool.tasks
            if hasattr(task, "_request")
        )
        == page_zero_task_count
    )


def test_clicking_named_destination_pdf_link_navigates_to_target_page(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "named-internal-link.pdf"
    _create_sample_pdf(source_path)

    def _fake_get_links(page: pymupdf.Page) -> list[dict[str, object]]:
        if page.number == 0:
            return [
                {
                    "from": pymupdf.Rect(72, 140, 152, 164),
                    "nameddest": "chapter-2",
                },
            ]
        return []

    def _fake_resolve_link(
        document: pymupdf.Document,
        uri: str | None = None,
        chapters: int = 0,
    ) -> tuple[int, float, float]:
        del document, chapters
        if uri == "#nameddest=chapter-2":
            return 1, 20.0, 250.0
        return -1, 0.0, 0.0

    monkeypatch.setattr(pymupdf.Page, "get_links", _fake_get_links)
    monkeypatch.setattr(pymupdf.Document, "resolve_link", _fake_resolve_link)

    window = MainWindow()
    window._thread_pool = _ImmediateThreadPool()
    window.resize(900, 500)
    window.show()
    _app().processEvents()

    window._open_document(source_path)
    _app().processEvents()
    page_label = window._page_labels[0]

    assert isinstance(page_label, PageSurfaceLabel)
    assert window._document.state.current_page_index == 0

    inset = PAGE_CONTENT_CHROME / 2
    page_label.mousePressEvent(
        _mouse_press_event(x=90 + inset, y=150 + inset),
    )
    _app().processEvents()

    target_page_label = window._page_labels[1]
    target_content_y = target_page_label.y() + round(
        target_page_label.height() - inset - 250
    )
    scroll_value = window._document_scroll_area.verticalScrollBar().value()

    assert window._document.state.current_page_index == 1
    assert target_content_y - scroll_value == 40


def test_pdf_link_destination_zoom_is_applied(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "zoom-link.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    applied_zooms: list[float] = []

    def _fake_apply_zoom(target_zoom: float) -> None:
        applied_zooms.append(target_zoom)
        window._document.state.set_zoom(target_zoom)

    monkeypatch.setattr(window, "_apply_zoom", _fake_apply_zoom)

    window._handle_page_link_activated(
        PdfPageLink(
            bounds=(72.0, 140.0, 152.0, 164.0),
            target_page_index=1,
            target_point=(20.0, 250.0),
            target_zoom=2.0,
        ),
    )

    assert applied_zooms == [2.0]
    assert window._document.state.zoom == 2.0
    assert window._document.state.current_page_index == 1


def test_clicking_pdf_file_link_opens_target_pdf_in_app(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "linked-source.pdf"
    target_path = tmp_path / "linked-target.pdf"
    _create_sample_pdf(source_path)
    _create_sample_pdf(target_path)

    def _fake_resolve_link(
        document: pymupdf.Document,
        uri: str | None = None,
        chapters: int = 0,
    ) -> tuple[int, float, float]:
        del document, chapters
        if uri == "#nameddest=chapter-2":
            return 1, 20.0, 250.0
        return -1, 0.0, 0.0

    opened_urls: list[str] = []
    monkeypatch.setattr(pymupdf.Document, "resolve_link", _fake_resolve_link)
    monkeypatch.setattr(
        page_links_module.QDesktopServices,
        "openUrl",
        lambda url: opened_urls.append(url.toString()) or True,
    )

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    window._handle_page_link_activated(
        PdfPageLink(
            bounds=(0.0, 0.0, 1.0, 1.0),
            named_destination="chapter-2",
            file_path=target_path.name,
        ),
    )

    assert opened_urls == []
    assert window._document.source_path == target_path.resolve(strict=False)
    assert window._document.state.current_page_index == 1
    assert window._document_tabs.count() == 2


def test_clicking_local_non_pdf_file_link_opens_externally(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "source.pdf"
    notes_path = tmp_path / "notes.txt"
    _create_sample_pdf(source_path)
    notes_path.write_text("hello", encoding="utf-8")

    opened_urls: list[str] = []
    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    monkeypatch.setattr(
        page_links_module.QDesktopServices,
        "openUrl",
        lambda url: opened_urls.append(url.toLocalFile()) or True,
    )

    window._open_document(source_path)
    window._handle_page_link_activated(
        PdfPageLink(
            bounds=(0.0, 0.0, 1.0, 1.0),
            file_path="notes.txt",
        ),
    )

    assert [Path(path) for path in opened_urls] == [
        notes_path.resolve(strict=False),
    ]
    assert window._document.source_path == source_path


def test_clicking_file_link_with_non_file_scheme_is_ignored(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "source.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)
    monkeypatch.setattr(
        page_links_module.QDesktopServices,
        "openUrl",
        lambda _url: (_ for _ in ()).throw(
            AssertionError("Suspicious file links should not open externally."),
        ),
    )
    monkeypatch.setattr(
        window,
        "open_document_in_tab",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("Suspicious file links should not open internally."),
        ),
    )

    window._handle_page_link_activated(
        PdfPageLink(
            bounds=(0.0, 0.0, 1.0, 1.0),
            file_path="https://example.com/attack.pdf",
        ),
    )

    assert window._document.source_path == source_path


def test_toolbar_keeps_edit_button_and_read_mode_indicator() -> None:
    _app()
    window = MainWindow()

    toolbar = window.findChild(QToolBar)

    assert toolbar is not None
    assert window._rotate_right_action.text() == "Rotate Right"
    assert window._find_action.text() == "Find"
    assert window._previous_match_action.text() == "Previous Match"
    assert window._next_match_action.text() == "Next Match"
    assert isinstance(window._mouse_mode_indicator, QToolButton)
    assert window._mouse_mode_indicator.text() == "Mode: Read"
    assert window._search_bar.isHidden() is True

    toolbar_action_texts = [
        action.text() for action in toolbar.actions() if action.text()
    ]

    assert toolbar_action_texts == ["Fit Page"]


def test_thumbnail_arrow_buttons_reorder_selected_page(tmp_path: Path) -> None:
    _app()
    source_path = tmp_path / "reorder.pdf"
    _create_three_page_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    assert window._move_page_up_button.isEnabled() is False
    assert window._move_page_down_button.isEnabled() is True

    window._thumbnail_list.setCurrentRow(1)
    assert window._move_page_up_button.isEnabled() is True
    assert window._move_page_down_button.isEnabled() is True

    window._move_page_down_button.click()

    assert window._document.state.current_page_index == 2
    assert window._thumbnail_list.currentRow() == 2
    assert window._move_page_up_button.isEnabled() is True
    assert window._move_page_down_button.isEnabled() is False
    assert window._document.is_dirty() is True
    assert "page 3" in window._document.page_text(1)
    assert "page 2" in window._document.page_text(2)


def test_find_is_the_only_remaining_keyboard_shortcut() -> None:
    _app()
    window = MainWindow()

    assert window._find_action.shortcut().toString() == "Ctrl+F"

    actions_without_shortcuts = [
        window._open_action,
        window._save_action,
        window._save_as_action,
        window._previous_page_shortcut_action,
        window._next_page_shortcut_action,
        window._zoom_out_shortcut_action,
        window._zoom_in_shortcut_action,
        window._actual_size_action,
        window._fit_width_action,
        window._fit_page_action,
        window._single_page_view_action,
        window._previous_match_action,
        window._next_match_action,
    ]

    assert all(
        action.shortcut().isEmpty() for action in actions_without_shortcuts
    )
    assert window._close_tab_action.shortcut().toString() == "Ctrl+W"
    assert window._exit_action.shortcut().isEmpty() is True


def test_find_action_reveals_search_bar(tmp_path: Path) -> None:
    _app()
    source_path = tmp_path / "search-reveal.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    assert window._search_bar.isHidden() is True

    window._find_action.trigger()

    assert window._search_bar.isHidden() is False


def test_hide_search_bar_clears_query_and_matches(tmp_path: Path) -> None:
    _app()
    source_path = tmp_path / "search-hide.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _ImmediateThreadPool()
    window._open_document(source_path)
    window._find_action.trigger()
    window._search_input.setText("first")

    window._run_search()

    assert window._search.matches

    window._hide_search_bar()

    assert window._search_bar.isHidden() is True
    assert window._search_input.text() == ""
    assert window._search.matches == []


def test_search_updates_as_user_types(tmp_path: Path) -> None:
    _app()
    source_path = tmp_path / "search-live.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _ImmediateThreadPool()
    window._open_document(source_path)
    window._find_action.trigger()

    window._search_input.setText("first")
    window._handle_search_text_changed("first")
    window._search_debounce_timer.stop()
    window._run_search()

    assert len(window._search.matches) == 1
    assert window._search.matches[0].page_index == 0
    assert window._search_status_label.text() == "1/1"


def test_escape_hides_search_bar(tmp_path: Path) -> None:
    _app()
    source_path = tmp_path / "search-escape.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)
    window._find_action.trigger()
    window._search_input.setText("first")

    escape_event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Escape,
        Qt.KeyboardModifier.NoModifier,
    )

    handled = window.eventFilter(window._search_input, escape_event)

    assert handled is True
    assert window._search_bar.isHidden() is True
    assert window._search_input.text() == ""


def test_thumbnail_viewport_show_and_resize_events_refresh_visible_range(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "thumbnail-viewport-events.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    refresh_calls: list[QEvent.Type] = []

    def _record_refresh() -> None:
        refresh_calls.append(current_event_type)

    window._refresh_visible_thumbnails = _record_refresh  # type: ignore[method-assign]

    current_event_type = QEvent.Type.Show
    show_handled = window.eventFilter(
        window._thumbnail_list.viewport(),
        QEvent(QEvent.Type.Show),
    )

    current_event_type = QEvent.Type.Resize
    resize_handled = window.eventFilter(
        window._thumbnail_list.viewport(),
        QEvent(QEvent.Type.Resize),
    )

    assert show_handled is False
    assert resize_handled is False
    assert refresh_calls == [QEvent.Type.Show, QEvent.Type.Resize]


def test_scrolling_ignores_stale_page_geometry_cache(tmp_path: Path) -> None:
    _app()
    source_path = tmp_path / "geometry.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    window._page_top_offsets = []
    window._page_bottom_offsets = []

    window._handle_document_scrolled(0)


def test_single_page_view_shows_only_current_page(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "single-page-view.pdf"
    _create_three_page_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    assert len(window._page_labels) == 3
    assert window._visible_page_indexes == [0, 1, 2]

    window._single_page_view_action.trigger()

    assert window._single_page_view_action.isChecked() is True
    assert len(window._page_labels) == 1
    assert window._visible_page_indexes == [0]

    window._page_selector.setValue(2)

    assert window._document.state.current_page_index == 1
    assert len(window._page_labels) == 1
    assert window._visible_page_indexes == [1]

    window._single_page_view_action.trigger()

    assert window._single_page_view_action.isChecked() is False
    assert window._document.state.current_page_index == 1
    assert len(window._page_labels) == 3
    assert window._visible_page_indexes == [0, 1, 2]


def test_single_page_view_keeps_thumbnail_navigation(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "single-page-thumbnails.pdf"
    _create_three_page_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    window._single_page_view_action.trigger()
    window._thumbnail_list.setCurrentRow(2)

    assert window._document.state.current_page_index == 2
    assert len(window._page_labels) == 1
    assert window._visible_page_indexes == [2]
    assert window._thumbnail_list.currentRow() == 2


def test_single_page_view_uses_up_down_for_page_steps(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "single-page-keys.pdf"
    _create_three_page_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)
    viewport = window._document_scroll_area.viewport()

    normal_down = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Down,
        Qt.KeyboardModifier.NoModifier,
    )
    assert window.eventFilter(viewport, normal_down) is False

    window._single_page_view_action.trigger()

    down_event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Down,
        Qt.KeyboardModifier.NoModifier,
    )
    assert window.eventFilter(viewport, down_event) is True
    assert window._document.state.current_page_index == 1
    assert window._visible_page_indexes == [1]

    up_event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Up,
        Qt.KeyboardModifier.NoModifier,
    )
    assert window.eventFilter(viewport, up_event) is True
    assert window._document.state.current_page_index == 0
    assert window._visible_page_indexes == [0]


def test_zoom_keeps_current_page_visible_after_rerender(
    tmp_path: Path,
) -> None:
    app = _app()
    source_path = tmp_path / "zoom-rerender.pdf"
    document = pymupdf.open()
    try:
        for page_number in range(4):
            page = document.new_page()
            page.insert_text((72, 72), f"page {page_number + 1}")
        document.save(source_path)
    finally:
        document.close()

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.show()
    window._open_document(source_path)
    app.processEvents()

    window._document.go_to_page(2)
    window._sync_current_page_ui(scroll_to_page=True)
    app.processEvents()

    assert window._document.state.current_page_index == 2

    window._change_zoom(zoom_in=True)
    app.processEvents()

    assert window._document.state.current_page_index == 2
    assert window._document_scroll_area.verticalScrollBar().value() > 0


def test_zoom_preserves_page_point_under_mouse_anchor(
    tmp_path: Path,
) -> None:
    app = _app()
    source_path = tmp_path / "zoom-mouse-anchor.pdf"
    document = pymupdf.open()
    try:
        for page_number in range(4):
            page = document.new_page(width=320, height=240)
            page.insert_text((40, 40), f"page {page_number + 1}")
        document.save(source_path)
    finally:
        document.close()

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.show()
    window._open_document(source_path)
    app.processEvents()

    vertical_bar = window._document_scroll_area.verticalScrollBar()
    target_page_label = window._page_labels[2]
    vertical_bar.setValue(max(target_page_label.y() - 40, 0))
    window._document.go_to_page(0, record_history=False)
    app.processEvents()

    viewport = window._document_scroll_area.viewport()
    anchor_position = QPointF(
        viewport.width() / 2,
        target_page_label.y() - vertical_bar.value() + 80,
    )

    def anchor_snapshot() -> tuple[int, float, float]:
        content_x = (
            window._document_scroll_area.horizontalScrollBar().value()
            + anchor_position.x()
        )
        content_y = vertical_bar.value() + anchor_position.y()
        for page_index, page_label in enumerate(window._page_labels):
            page_left = float(page_label.x())
            page_top = float(page_label.y())
            page_right = page_left + page_label.width()
            page_bottom = page_top + page_label.height()
            if not (
                page_left <= content_x <= page_right
                and page_top <= content_y <= page_bottom
            ):
                continue

            inset = PAGE_CONTENT_CHROME / 2
            content_width = max(page_label.width() - PAGE_CONTENT_CHROME, 1)
            content_height = max(page_label.height() - PAGE_CONTENT_CHROME, 1)
            relative_x = (
                min(
                    max(content_x - page_left - inset, 0.0),
                    content_width,
                )
                / content_width
            )
            relative_y = (
                min(
                    max(content_y - page_top - inset, 0.0),
                    content_height,
                )
                / content_height
            )
            return page_index, relative_x, relative_y

        msg = "Mouse anchor is not positioned over any page label."
        raise AssertionError(msg)

    before_page_index, before_x_ratio, before_y_ratio = anchor_snapshot()

    window._change_zoom(
        zoom_in=True,
        anchor_position=anchor_position,
    )
    app.processEvents()

    after_page_index, after_x_ratio, after_y_ratio = anchor_snapshot()

    assert before_page_index == 2
    assert after_page_index == before_page_index
    assert after_x_ratio == pytest.approx(before_x_ratio, abs=0.03)
    assert after_y_ratio == pytest.approx(before_y_ratio, abs=0.03)


def test_ctrl_wheel_zoom_uses_smaller_increment_than_shortcut_zoom(
    tmp_path: Path,
) -> None:
    app = _app()
    source_path = tmp_path / "ctrl-wheel-zoom.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.show()
    window._open_document(source_path)
    app.processEvents()

    viewport = window._document_scroll_area.viewport()
    anchor = QPointF(viewport.width() / 2, viewport.height() / 2)
    wheel_event = _ctrl_wheel_event(
        x=anchor.x(),
        y=anchor.y(),
        angle_delta_y=120,
    )

    handled = window.eventFilter(viewport, wheel_event)
    app.processEvents()

    assert handled is True
    assert window._document.state.zoom == pytest.approx(1.1, abs=0.001)


def test_ctrl_wheel_zoom_keeps_visible_page_when_mouse_is_in_margin(
    tmp_path: Path,
) -> None:
    app = _app()
    source_path = tmp_path / "ctrl-wheel-margin-anchor.pdf"
    document = pymupdf.open()
    try:
        for page_number in range(4):
            page = document.new_page(width=320, height=240)
            page.insert_text((40, 40), f"page {page_number + 1}")
        document.save(source_path)
    finally:
        document.close()

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.resize(1200, 900)
    window.show()
    window._open_document(source_path)
    app.processEvents()

    vertical_bar = window._document_scroll_area.verticalScrollBar()
    target_page_label = window._page_labels[2]
    vertical_bar.setValue(max(target_page_label.y() - 40, 0))
    window._document.go_to_page(0, record_history=False)
    app.processEvents()

    viewport = window._document_scroll_area.viewport()
    anchor_x = min(
        float(target_page_label.x() + target_page_label.width()) + 20.0,
        float(viewport.width() - 1),
    )
    anchor_y = target_page_label.y() - vertical_bar.value() + 80
    wheel_event = _ctrl_wheel_event(
        x=anchor_x,
        y=anchor_y,
        angle_delta_y=120,
    )

    handled = window.eventFilter(viewport, wheel_event)
    app.processEvents()

    assert handled is True
    assert window._document.state.current_page_index == 2
    assert window._document_scroll_area.verticalScrollBar().value() > 0


def test_ctrl_wheel_zoom_burst_keeps_current_page(tmp_path: Path) -> None:
    app = _app()
    source_path = tmp_path / "ctrl-wheel-burst.pdf"
    document = pymupdf.open()
    try:
        for page_number in range(6):
            page = document.new_page()
            page.insert_text((72, 72), f"page {page_number + 1}")
        document.save(source_path)
    finally:
        document.close()

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.resize(1200, 900)
    window.show()
    window._open_document(source_path)
    app.processEvents()

    window._document.go_to_page(2)
    window._sync_current_page_ui(scroll_to_page=True)
    app.processEvents()

    viewport = window._document_scroll_area.viewport()
    anchor = QPointF(viewport.width() / 2, viewport.height() / 2)

    # Two wheel notches in the same event-loop turn: the second arrives
    # before the first zoom's deferred scroll restore has run.
    for _ in range(2):
        wheel_event = _ctrl_wheel_event(
            x=anchor.x(),
            y=anchor.y(),
            angle_delta_y=120,
        )
        window.eventFilter(viewport, wheel_event)
    app.processEvents()
    app.processEvents()

    assert window._document.state.current_page_index == 2
    assert window._document_scroll_area.verticalScrollBar().value() > 0


def test_ctrl_wheel_zoom_reuses_page_labels_until_the_gesture_settles(
    tmp_path: Path,
) -> None:
    app = _app()
    source_path = tmp_path / "ctrl-wheel-preview.pdf"
    _create_three_page_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _ImmediateThreadPool()
    window.resize(1200, 900)
    window.show()
    window._open_document(source_path)
    app.processEvents()

    labels_before = list(window._page_labels)
    generation_before = window._generations.render
    zoom_before = window._document.state.zoom
    viewport = window._document_scroll_area.viewport()

    for _ in range(3):
        wheel_event = _ctrl_wheel_event(
            x=viewport.width() / 2,
            y=viewport.height() / 2,
            angle_delta_y=120,
        )
        assert window.eventFilter(viewport, wheel_event) is True
    app.processEvents()

    assert window._document.state.zoom > zoom_before
    assert window._page_labels == labels_before
    assert window._generations.render == generation_before
    assert window._zoom_settle_timer.isActive() is True

    window._settle_zoom_preview()
    app.processEvents()

    assert window._generations.render > generation_before
    assert window._page_labels == labels_before
    assert window._zoom_preview_gesture is None


def test_ctrl_wheel_zoom_preview_resizes_pages_like_a_rebuild(
    tmp_path: Path,
) -> None:
    app = _app()
    source_path = tmp_path / "ctrl-wheel-preview-size.pdf"
    _create_three_page_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.resize(1200, 900)
    window.show()
    window._open_document(source_path)
    app.processEvents()

    viewport = window._document_scroll_area.viewport()
    for _ in range(4):
        wheel_event = _ctrl_wheel_event(
            x=viewport.width() / 2,
            y=viewport.height() / 2,
            angle_delta_y=120,
        )
        window.eventFilter(viewport, wheel_event)
    app.processEvents()

    preview_sizes = [label.size() for label in window._page_labels]

    # A full rebuild at the same zoom is the reference layout; repeated
    # preview notches must not drift away from it.
    window._build_page_placeholders()
    app.processEvents()

    assert [label.size() for label in window._page_labels] == preview_sizes


def test_ctrl_wheel_zoom_uses_trackpad_pixel_delta(tmp_path: Path) -> None:
    app = _app()
    source_path = tmp_path / "ctrl-wheel-pixel-delta.pdf"
    _create_three_page_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.resize(1200, 900)
    window.show()
    window._open_document(source_path)
    app.processEvents()

    zoom_before = window._document.state.zoom
    viewport = window._document_scroll_area.viewport()
    wheel_event = _ctrl_wheel_event(
        x=viewport.width() / 2,
        y=viewport.height() / 2,
        angle_delta_y=0,
        pixel_delta_y=25,
    )

    assert window.eventFilter(viewport, wheel_event) is True
    app.processEvents()

    # Half a notch of travel zooms by half a notch, not a whole one.
    assert zoom_before < window._document.state.zoom < zoom_before * 1.1


def test_toolbar_zoom_cancels_a_pending_wheel_zoom_settle(
    tmp_path: Path,
) -> None:
    app = _app()
    source_path = tmp_path / "ctrl-wheel-settle-cancel.pdf"
    _create_three_page_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.resize(1200, 900)
    window.show()
    window._open_document(source_path)
    app.processEvents()

    viewport = window._document_scroll_area.viewport()
    wheel_event = _ctrl_wheel_event(
        x=viewport.width() / 2,
        y=viewport.height() / 2,
        angle_delta_y=120,
    )
    window.eventFilter(viewport, wheel_event)
    app.processEvents()

    assert window._zoom_settle_timer.isActive() is True

    window._zoom_in()
    app.processEvents()

    assert window._zoom_settle_timer.isActive() is False
    assert window._zoom_preview_gesture is None


def test_ctrl_wheel_zoom_anchor_uses_document_page_in_single_page_view(
    tmp_path: Path,
) -> None:
    app = _app()
    source_path = tmp_path / "single-page-ctrl-wheel-anchor.pdf"
    _create_three_page_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.show()
    window._open_document(source_path)
    app.processEvents()

    window._single_page_view_action.trigger()
    window._document.go_to_page(2)
    window._sync_current_page_ui(scroll_to_page=True)
    app.processEvents()

    page_label = window._page_labels[0]
    anchor_position = QPointF(
        page_label.x() + page_label.width() / 2,
        page_label.y() + page_label.height() / 2,
    )

    scroll_restore = window._capture_zoom_scroll_restore(
        anchor_position=anchor_position,
        previous_zoom=window._document.state.zoom,
        updated_zoom=window._document.state.zoom * 1.1,
    )

    assert window._visible_page_indexes == [2]
    assert scroll_restore.restore_page_index == 2
    assert scroll_restore.page_anchor is not None
    assert scroll_restore.page_anchor.page_index == 2


def test_thumbnail_context_menu_can_delete_a_page(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "delete-thumbnail.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(
            lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
        ),
    )

    assert window._thumbnail_list.contextMenuPolicy() == (
        Qt.ContextMenuPolicy.CustomContextMenu
    )
    assert window._thumbnail_list.count() == 2

    window._delete_thumbnail_page(0)

    assert window._document.state.page_count == 1
    assert window._document.state.current_page_index == 0
    assert window._thumbnail_list.count() == 1
    assert "second page" in window._document.page_text(0)
    assert window._save_action.isEnabled() is True


def test_thumbnail_context_menu_can_rotate_its_page(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app = _app()
    source_path = tmp_path / "rotate-thumbnail.pdf"
    _create_sample_pdf(source_path)
    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window.show()
    window._open_document(source_path)
    app.processEvents()

    monkeypatch.setattr(thumbnails_module, "QMenu", _FakeContextMenu)
    item = window._thumbnail_list.item(1)

    window._show_thumbnail_context_menu(
        window._thumbnail_list.visualItemRect(item).center(),
    )

    assert window._document.state.current_page_index == 1
    assert window._document.current_page().rotation == 90
    assert window._save_action.isEnabled() is True


def test_page_delete_renders_both_views_from_edited_document(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "delete-last-page.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)
    window._thread_pool = _FailingThreadPool()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(
            lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
        ),
    )

    window._delete_thumbnail_page(1)

    page_pixmap = window._page_labels[0].pixmap()
    thumbnail_item = window._thumbnail_list.item(0)
    assert page_pixmap is not None
    assert not page_pixmap.isNull()
    assert thumbnail_item is not None
    assert not thumbnail_item.icon().isNull()


def test_dirty_document_search_uses_in_memory_state(tmp_path: Path) -> None:
    _app()
    source_path = tmp_path / "dirty-search.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    try:
        window._thread_pool = _NoOpThreadPool()
        window._open_document(source_path)
        window._document.delete_page(0)
        window._search_input.setText("first page")
        window._thread_pool = _ImmediateThreadPool()

        window._run_search()

        assert window._search.matches == []
        assert "No matches found" in window.statusBar().currentMessage()
    finally:
        window._document.close_document()


def test_view_menu_toggles_panes() -> None:
    _app()
    window = MainWindow()

    window._bookmarks_pane_action.setChecked(False)
    window._thumbnails_pane_action.setChecked(False)
    window._text_pane_action.setChecked(False)

    assert window._bookmark_tree.isHidden()
    assert window._thumbnail_pane.isHidden()
    assert window._page_text.isHidden()

    window._bookmarks_pane_action.setChecked(True)
    window._thumbnails_pane_action.setChecked(True)
    window._text_pane_action.setChecked(True)

    assert not window._bookmark_tree.isHidden()
    assert not window._thumbnail_pane.isHidden()
    assert not window._page_text.isHidden()


def test_text_selection_mode_allows_bookmark_from_selected_text(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "selection-bookmark.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    selection_flags = window._page_text.textInteractionFlags()
    assert (
        bool(
            selection_flags & Qt.TextInteractionFlag.TextSelectableByMouse,
        )
        is True
    )

    text_cursor = window._page_text.textCursor()
    text_cursor.setPosition(0)
    text_cursor.movePosition(
        text_cursor.MoveOperation.EndOfWord,
        text_cursor.MoveMode.KeepAnchor,
    )
    window._page_text.setTextCursor(text_cursor)

    window._add_bookmark_from_selected_text()

    assert window._bookmark_tree.topLevelItemCount() == 1
    assert window._bookmark_tree.topLevelItem(0).text(0) == "first"
    assert window._save_action.isEnabled() is True


def test_text_selection_mode_updates_toolbar_indicator_and_page_overlay(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "page-overlay.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    page_label = window._page_labels[0]

    assert isinstance(page_label, PageSurfaceLabel)
    assert page_label.text_layer().isHidden() is False
    assert window._mouse_mode_indicator.text() == "Mode: Read"

    window._text_selection_mouse_mode_action.trigger()

    assert page_label.text_layer().isHidden() is False
    assert window._mouse_mode_indicator.text() == "Mode: Read"


def test_lazy_text_overlay_failures_are_logged_once_per_label_generation(
    monkeypatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "page-words-failure.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)
    window._text_selection_mouse_mode_action.trigger()

    page_words_calls: list[int] = []

    def _raise_page_words(page_index: int | None = None):
        page_words_calls.append(-1 if page_index is None else page_index)
        msg = "synthetic page word extraction failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(window._document, "page_words", _raise_page_words)

    with caplog.at_level(
        logging.ERROR,
        logger=selection_module.__name__,
    ):
        window._ensure_page_words_loaded(0)
        window._ensure_page_words_loaded(0)

    assert page_words_calls == [0]
    assert 0 in window._words_loaded_pages
    assert "Failed to load text overlay for page 1" in caplog.text


def test_toolbar_mouse_mode_indicator_toggles_modes(tmp_path: Path) -> None:
    _app()
    source_path = tmp_path / "toggle-mode.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    assert window._is_text_selection_mode is True
    assert window._mouse_mode_indicator.text() == "Mode: Read"


def test_edit_pdf_action_switches_to_edit_mode(tmp_path: Path) -> None:
    _app()
    source_path = tmp_path / "edit-mode.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    window._edit_pdf_action.trigger()

    assert window._is_pdf_edit_mode is True
    assert window._is_text_selection_mode is False
    assert window._mouse_mode_indicator.text() == "Mode: Edit PDF"

    window._mouse_mode_indicator.click()

    assert window._is_text_selection_mode is True
    assert window._mouse_mode_indicator.text() == "Mode: Read"

    window._mouse_mode_indicator.click()

    assert window._is_text_selection_mode is True
    assert window._mouse_mode_indicator.text() == "Mode: Read"


def test_page_overlay_selection_can_add_bookmark(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "page-overlay-bookmark.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _ImmediateThreadPool()
    window._open_document(source_path)
    window._text_selection_mouse_mode_action.trigger()

    page_label = window._page_labels[0]

    assert isinstance(page_label, PageSurfaceLabel)

    page_label.text_layer().select_word_range(0, 0)

    window._add_bookmark_from_selected_text(
        page_label.selected_text(),
        page_index=0,
    )

    assert window._bookmark_tree.topLevelItemCount() == 1
    assert window._bookmark_tree.topLevelItem(0).text(0) == "first"


def test_page_overlay_context_menu_includes_selection_actions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "page-overlay-context-menu.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _ImmediateThreadPool()
    window._open_document(source_path)
    window._text_selection_mouse_mode_action.trigger()

    page_label = window._page_labels[0]

    assert isinstance(page_label, PageSurfaceLabel)

    page_label.text_layer().select_word_range(0, 0)

    captured_action_texts: list[str] = []

    def _fake_popup(self, *_args, **_kwargs):
        captured_action_texts.extend(
            action.text()
            for action in self.actions()
            if not action.isSeparator()
        )
        self.close()

    monkeypatch.setattr(QMenu, "popup", _fake_popup)

    window._show_page_surface_context_menu(
        page_index=0,
        page_label=page_label,
        position=page_label.text_layer().rect().center(),
    )

    assert captured_action_texts == [
        "Copy",
        "Select All",
        "Add Bookmark From Selection",
        "Replace Text...",
        "Remove Content",
    ]


def test_edit_pdf_action_redacts_selected_rectangle(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "edit-pdf-redact-selection.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _ImmediateThreadPool()
    window._open_document(source_path)

    window._edit_pdf_action.trigger()

    assert window._is_pdf_edit_mode is True

    page_label = window._page_labels[0]

    assert isinstance(page_label, PageSurfaceLabel)

    page_label.select_region_rectangle((60.0, 60.0, 120.0, 90.0))

    window._remove_selected_text_action.trigger()

    updated_text = window._document.page_text(0)

    assert "first" not in updated_text
    assert "page" not in updated_text
    assert window._document.is_dirty() is True
    assert window._save_action.isEnabled() is True


def test_remove_content_toolbar_action_keeps_selected_page_active(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "edit-pdf-keep-page.pdf"
    _create_three_page_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _ImmediateThreadPool()
    window._open_document(source_path)
    window._edit_pdf_action.trigger()

    page_label = window._page_labels[1]

    assert isinstance(page_label, PageSurfaceLabel)

    page_label.select_region_rectangle((60.0, 60.0, 120.0, 90.0))

    window._remove_selected_text_action.trigger()

    assert window._document.state.current_page_index == 1
    assert window._thumbnail_list.spacing() == 8
    assert window._thumbnail_list.gridSize().width() >= (
        window._thumbnail_item_size().width()
    )
    assert window._thumbnail_list.gridSize().height() == (
        window._thumbnail_item_size().height()
    )
    assert all(
        window._thumbnail_list.item(row).sizeHint()
        == window._thumbnail_list.gridSize()
        for row in range(window._thumbnail_list.count())
    )


def test_remove_content_keeps_scroll_near_selected_page_region(
    tmp_path: Path,
) -> None:
    app = _app()
    source_path = tmp_path / "edit-pdf-keep-scroll.pdf"
    _create_three_page_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _ImmediateThreadPool()
    window.resize(700, 400)
    window.show()
    window._open_document(source_path)
    app.processEvents()

    window._edit_pdf_action.trigger()
    page_label = window._page_labels[1]

    assert isinstance(page_label, PageSurfaceLabel)

    window._document_scroll_area.verticalScrollBar().setValue(
        max(page_label.y() - 40, 0),
    )
    app.processEvents()
    original_scroll_value = (
        window._document_scroll_area.verticalScrollBar().value()
    )

    page_label.select_region_rectangle((60.0, 60.0, 120.0, 90.0))

    window._remove_selected_text_action.trigger()
    app.processEvents()

    assert window._document.state.current_page_index == 1
    assert (
        window._document_scroll_area.verticalScrollBar().value()
        == original_scroll_value
    )


def test_bookmark_context_menu_can_rename_bookmark(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "rename-bookmark-ui.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)
    window._document.add_bookmark("Original bookmark", page_index=0)
    window._populate_bookmarks()

    item = window._bookmark_tree.topLevelItem(0)

    assert item is not None

    monkeypatch.setattr(
        window,
        "_prompt_for_bookmark_title",
        lambda current_title: "Renamed bookmark",
    )

    captured_action_texts: list[str] = []

    class _CapturingContextMenu(_FakeContextMenu):
        def exec(self, *_args, **_kwargs):
            captured_action_texts.extend(
                action.text()
                for action in self.actions()
                if not action.isSeparator()
            )
            return super().exec()

    monkeypatch.setattr(bookmarks_module, "QMenu", _CapturingContextMenu)

    window._show_bookmark_context_menu(
        window._bookmark_tree.visualItemRect(item).center(),
    )

    assert captured_action_texts == ["Rename Bookmark", "Delete Bookmark"]
    assert window._bookmark_tree.topLevelItem(0).text(0) == "Renamed bookmark"


def test_bookmark_context_menu_can_delete_bookmark(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "delete-bookmark-ui.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)
    window._document.add_bookmark("Delete me", page_index=0)
    window._document.add_bookmark("Keep me", page_index=1)
    window._populate_bookmarks()

    item = window._bookmark_tree.topLevelItem(0)

    assert item is not None

    monkeypatch.setattr(
        bookmarks_module.QMessageBox,
        "question",
        lambda *_args, **_kwargs: (
            bookmarks_module.QMessageBox.StandardButton.Yes
        ),
    )

    class _DeleteBookmarkContextMenu(_FakeContextMenu):
        def exec(self, *_args, **_kwargs):
            return self.actions()[1]

    monkeypatch.setattr(bookmarks_module, "QMenu", _DeleteBookmarkContextMenu)

    window._show_bookmark_context_menu(
        window._bookmark_tree.visualItemRect(item).center(),
    )

    assert window._bookmark_tree.topLevelItemCount() == 1
    assert window._bookmark_tree.topLevelItem(0).text(0) == "Keep me"


def test_pane_visibility_persists_between_windows() -> None:
    _app()
    first_window = MainWindow()

    first_window._bookmarks_pane_action.setChecked(False)
    first_window._text_pane_action.setChecked(False)
    first_window._notes_pane_action.setChecked(False)
    first_window.close()

    persisted_settings = json.loads(
        app_module._PANE_SETTINGS_PATH.read_text(encoding="utf-8"),
    )

    assert persisted_settings == {
        "bookmarks_visible": False,
        "thumbnails_visible": True,
        "text_visible": False,
        "notes_visible": False,
        "text_selection_mode": True,
        "thumbnails_on_left": False,
    }

    second_window = MainWindow()

    assert second_window._bookmarks_pane_action.isChecked() is False
    assert second_window._bookmark_tree.isHidden() is True
    assert second_window._thumbnails_pane_action.isChecked() is True
    assert second_window._thumbnail_list.isHidden() is False
    assert second_window._text_pane_action.isChecked() is False
    assert second_window._page_text.isHidden() is True
    assert second_window._notes_pane_action.isChecked() is False
    assert second_window._notes_text.isHidden() is True


def test_notes_pane_edits_are_saved_inside_pdf(tmp_path: Path) -> None:
    _app()
    source_path = tmp_path / "notes-pane.pdf"
    _create_sample_pdf(source_path)
    window = MainWindow(initial_path=source_path)

    for partial_text in ("h", "he", "hel", "hell", "hello world"):
        window._notes_text.setPlainText(partial_text)

    assert window._document.is_dirty() is True
    assert window._save_action.isEnabled() is True
    assert window._document_tabs.tabText(0) == "* notes-pane.pdf"
    assert window.windowTitle() == "Open PDF - * notes-pane.pdf"

    window._save()
    window.close()

    reopened_window = MainWindow(initial_path=source_path)

    assert reopened_window._notes_text.toPlainText() == "hello world"
    assert reopened_window._document.is_dirty() is False


def test_mouse_mode_persists_between_windows() -> None:
    _app()
    first_window = MainWindow()

    first_window._browse_mouse_mode_action.trigger()
    first_window.close()

    second_window = MainWindow()

    assert second_window._is_text_selection_mode is True
    assert second_window._text_selection_mouse_mode_action.isChecked() is False
    assert second_window._browse_mouse_mode_action.isChecked() is True
    assert second_window._mouse_mode_indicator.text() == "Mode: Read"


def test_side_pane_layout_persists_between_windows() -> None:
    _app()
    first_window = MainWindow()

    first_window._thumbnails_left_side_action.trigger()
    first_window.close()

    second_window = MainWindow()
    main_splitter = second_window.centralWidget()

    assert isinstance(main_splitter, QSplitter)
    assert second_window._thumbnails_on_left is True
    assert second_window._thumbnails_left_side_action.isChecked() is True
    assert second_window._bookmarks_left_side_action.isChecked() is False
    assert main_splitter.widget(0) is second_window._thumbnail_pane
    assert main_splitter.widget(2) is second_window._bookmark_tree


def test_save_as_switches_to_new_file(monkeypatch, tmp_path: Path) -> None:
    _app()
    source_path = tmp_path / "source.pdf"
    target_path = tmp_path / "saved-as.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow(initial_path=source_path)
    window._document.go_to_page(1)
    window._document.state.set_zoom(1.5)

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(
            lambda *_args, **_kwargs: (str(target_path), "PDF Files (*.pdf)")
        ),
    )

    window._save_as()

    assert window._document.source_path == target_path
    assert window._document.state.current_page_index == 1
    assert window._document.state.zoom == 1.5
    assert target_path.exists()


def test_rename_file_replaces_old_path(monkeypatch, tmp_path: Path) -> None:
    _app()
    source_path = tmp_path / "very long original name.pdf"
    target_path = tmp_path / "wiley gaap 2026.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow(initial_path=source_path)
    window._document.go_to_page(1)
    window._document.state.set_zoom(1.5)

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(
            lambda *_args, **_kwargs: (str(target_path), "PDF Files (*.pdf)")
        ),
    )

    window._rename_file()

    assert window._document.source_path == target_path
    assert window._document.state.current_page_index == 1
    assert window._document.state.zoom == 1.5
    assert target_path.exists()
    assert source_path.exists() is False


def test_rename_file_can_overwrite_existing_destination(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "very long original name.pdf"
    target_path = tmp_path / "wiley gaap 2026.pdf"
    _create_sample_pdf(source_path)
    _create_three_page_pdf(target_path)

    window = MainWindow(initial_path=source_path)

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(
            lambda *_args, **_kwargs: (str(target_path), "PDF Files (*.pdf)"),
        ),
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(
            lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
        ),
    )

    window._rename_file()

    assert window._document.source_path == target_path
    assert source_path.exists() is False
    assert target_path.exists()
    replacement_document = pymupdf.open(target_path)
    try:
        assert replacement_document.page_count == 2
    finally:
        replacement_document.close()


def test_rename_file_leaves_existing_destination_when_overwrite_cancelled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "very long original name.pdf"
    target_path = tmp_path / "wiley gaap 2026.pdf"
    _create_sample_pdf(source_path)
    _create_three_page_pdf(target_path)

    window = MainWindow(initial_path=source_path)

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(
            lambda *_args, **_kwargs: (str(target_path), "PDF Files (*.pdf)"),
        ),
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(
            lambda *_args, **_kwargs: QMessageBox.StandardButton.No,
        ),
    )

    window._rename_file()

    assert window._document.source_path == source_path
    assert source_path.exists()
    original_target_document = pymupdf.open(target_path)
    try:
        assert original_target_document.page_count == 3
    finally:
        original_target_document.close()


def test_properties_action_updates_pdf_metadata(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "properties.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)

    updated_info_dict = dict(window._document.metadata().info_dict)
    updated_info_dict["title"] = "Project Plan"
    updated_info_dict["author"] = "Alex Writer"
    updated_custom_info_dict = {"edition": "2"}
    updated_xmp_xml = (
        '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '    <rdf:Description rdf:about="" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        "      <dc:title>\n"
        "        <rdf:Alt>\n"
        '          <rdf:li xml:lang="x-default">Project Plan</rdf:li>\n'
        "        </rdf:Alt>\n"
        "      </dc:title>\n"
        "    </rdf:Description>\n"
        "  </rdf:RDF>\n"
        "</x:xmpmeta>\n"
        '<?xpacket end="w"?>'
    )

    monkeypatch.setattr(
        window,
        "_prompt_for_document_properties",
        lambda **_kwargs: (
            updated_info_dict,
            updated_custom_info_dict,
            updated_xmp_xml,
        ),
    )

    window._properties_action.trigger()

    metadata = window._document.metadata()

    assert metadata.title == "Project Plan"
    assert metadata.author == "Alex Writer"
    assert metadata.custom_info_dict == {"edition": "2"}
    assert metadata.xmp_xml == updated_xmp_xml
    assert window._save_action.isEnabled() is True


def test_properties_dialog_edits_custom_properties() -> None:
    _app()
    dialog = DocumentPropertiesDialog(
        current_info_dict={},
        current_custom_info_dict={"edition": "2"},
        current_xmp_xml="",
    )

    assert dialog._custom_table.rowCount() == 1
    assert dialog._custom_table.item(0, 0).text() == "edition"
    assert dialog._custom_table.item(0, 1).text() == "2"

    dialog._custom_table.selectRow(0)
    dialog._delete_custom_property()
    dialog._add_custom_property()
    dialog._custom_table.item(0, 0).setText("print_edition")
    dialog._custom_table.item(0, 1).setText("Second")

    _info_dict, custom_info_dict, _xmp_xml = dialog.values()

    assert custom_info_dict == {"print_edition": "Second"}


def test_rotate_rerenders_dirty_page_without_background_workers(
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "rotated.pdf"
    _create_single_page_pdf(source_path, width=200, height=100)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)
    window._thread_pool = _FailingThreadPool()

    window._rotate_current_page()

    page_label = window._page_labels[0]
    page_pixmap = page_label.pixmap()
    thumbnail_item = window._thumbnail_list.item(0)

    assert page_pixmap is not None
    assert not page_pixmap.isNull()
    assert page_label.width() == 110
    assert page_label.height() == 210
    assert thumbnail_item is not None
    assert thumbnail_item.icon().isNull() is False


def test_save_disables_save_action_after_success(tmp_path: Path) -> None:
    _app()
    source_path = tmp_path / "save.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()
    window._open_document(source_path)
    window._document.rotate_clockwise()
    window._refresh_actions()

    assert window._save_action.isEnabled() is True

    window._save()

    assert window._save_action.isEnabled() is False


def test_open_document_cancel_keeps_unsaved_document(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "source.pdf"
    next_path = tmp_path / "next.pdf"
    _create_sample_pdf(source_path)
    _create_sample_pdf(next_path)

    window = MainWindow()
    try:
        window._thread_pool = _NoOpThreadPool()
        window._open_document(source_path)
        window._document.rotate_clockwise()

        monkeypatch.setattr(
            QMessageBox,
            "question",
            staticmethod(
                lambda *_args, **_kwargs: QMessageBox.StandardButton.Cancel,
            ),
        )

        window._open_document(next_path)

        assert window._document.source_path == source_path
        assert window._document.is_dirty() is True
    finally:
        window._document.close_document()


def test_unsaved_changes_save_routes_to_save_as_when_needed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "source.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    try:
        window._thread_pool = _NoOpThreadPool()
        window._open_document(source_path)
        window._document.rotate_clockwise()

        save_calls: list[str] = []

        monkeypatch.setattr(
            QMessageBox,
            "question",
            staticmethod(
                lambda *_args, **_kwargs: QMessageBox.StandardButton.Save,
            ),
        )
        monkeypatch.setattr(window._document, "can_save", lambda: False)

        def fake_save() -> None:
            save_calls.append("save")

        def fake_save_as() -> None:
            save_calls.append("save_as")
            window._document._is_dirty = False

        monkeypatch.setattr(window, "_save", fake_save)
        monkeypatch.setattr(window, "_save_as", fake_save_as)

        assert window._confirm_unsaved_changes() is True
        assert save_calls == ["save_as"]
    finally:
        window._document.close_document()


def test_opening_second_document_creates_new_tab_and_preserves_first_state(
    tmp_path: Path,
) -> None:
    _app()
    first_path = tmp_path / "first.pdf"
    second_path = tmp_path / "second.pdf"
    _create_sample_pdf(first_path)
    _create_sample_pdf(second_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()

    window.open_document_in_tab(first_path)
    window._document.go_to_page(1)
    window._document.state.set_zoom(1.5)

    window.open_document_in_tab(second_path)

    assert window._document_tabs.count() == 2
    assert window._document_tabs.tabText(0) == "first.pdf"
    assert window._document_tabs.tabText(1) == "second.pdf"
    assert window._document.source_path == second_path

    window._activate_document_tab(0)

    assert window._document.source_path == first_path
    assert window._document.state.current_page_index == 1
    assert window._document.state.zoom == 1.5


def test_switching_tabs_restores_each_documents_notes(tmp_path: Path) -> None:
    _app()
    first_path = tmp_path / "first-notes.pdf"
    second_path = tmp_path / "second-notes.pdf"
    _create_sample_pdf(first_path)
    _create_sample_pdf(second_path)
    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()

    window.open_document_in_tab(first_path)
    window._notes_text.setPlainText("first document notes")
    window.open_document_in_tab(second_path)
    window._notes_text.setPlainText("second document notes")

    window._activate_document_tab(0)
    assert window._notes_text.toPlainText() == "first document notes"

    window._activate_document_tab(1)
    assert window._notes_text.toPlainText() == "second document notes"


def test_opening_existing_document_path_reuses_existing_tab(
    tmp_path: Path,
) -> None:
    _app()
    first_path = tmp_path / "first.pdf"
    second_path = tmp_path / "second.pdf"
    _create_sample_pdf(first_path)
    _create_sample_pdf(second_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()

    window.open_document_in_tab(first_path)
    window.open_document_in_tab(second_path)
    window.open_document_in_tab(first_path)

    assert window._document_tabs.count() == 2
    assert window._document_tabs.currentIndex() == 0
    assert window._document.source_path == first_path


def test_drag_reordering_tabs_preserves_session_state(tmp_path: Path) -> None:
    _app()
    first_path = tmp_path / "first.pdf"
    second_path = tmp_path / "second.pdf"
    _create_sample_pdf(first_path)
    _create_sample_pdf(second_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()

    window.open_document_in_tab(first_path)
    window._document.go_to_page(1)
    window._document.state.set_zoom(1.5)
    window.open_document_in_tab(second_path)
    window._document.go_to_page(1)
    window._document.state.set_zoom(2.0)

    window._document_tabs.moveTab(1, 0)

    assert window._document_tabs.tabText(0) == "second.pdf"
    assert window._document_tabs.tabText(1) == "first.pdf"
    assert window._document.source_path == second_path
    assert window._document.state.current_page_index == 1
    assert window._document.state.zoom == 2.0

    window._activate_document_tab(1)

    assert window._document.source_path == first_path
    assert window._document.state.current_page_index == 1
    assert window._document.state.zoom == 1.5


def test_close_tab_action_closes_current_document_tab(tmp_path: Path) -> None:
    _app()
    first_path = tmp_path / "first.pdf"
    second_path = tmp_path / "second.pdf"
    _create_sample_pdf(first_path)
    _create_sample_pdf(second_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()

    window.open_document_in_tab(first_path)
    window.open_document_in_tab(second_path)

    assert window._document.source_path == second_path

    window._close_tab_action.trigger()

    assert window._document_tabs.count() == 1
    assert window._document.source_path == first_path
    assert window._document_tabs.currentIndex() == 0


def test_duplicate_filenames_use_full_paths_in_tab_labels(
    tmp_path: Path,
) -> None:
    _app()
    first_directory = tmp_path / "first"
    second_directory = tmp_path / "second"
    first_directory.mkdir()
    second_directory.mkdir()
    first_path = first_directory / "shared.pdf"
    second_path = second_directory / "shared.pdf"
    _create_sample_pdf(first_path)
    _create_sample_pdf(second_path)

    window = MainWindow()
    window._thread_pool = _NoOpThreadPool()

    window.open_document_in_tab(first_path)
    window.open_document_in_tab(second_path)

    assert window._document_tabs.tabText(0) == str(first_path)
    assert window._document_tabs.tabText(1) == str(second_path)


def test_close_event_cancel_keeps_unsaved_document_open(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "source.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    try:
        window._thread_pool = _NoOpThreadPool()
        window._open_document(source_path)
        window._document.rotate_clockwise()

        monkeypatch.setattr(
            QMessageBox,
            "question",
            staticmethod(
                lambda *_args, **_kwargs: QMessageBox.StandardButton.Cancel,
            ),
        )

        event = QCloseEvent()
        window.closeEvent(event)

        assert event.isAccepted() is False
        assert window._document.is_dirty() is True
    finally:
        window._document.close_document()


def test_save_releases_cached_render_handles_before_writing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "save-handles.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    try:
        window._thread_pool = _NoOpThreadPool()
        window._open_document(source_path)
        window._document.rotate_clockwise()

        events: list[str] = []
        monkeypatch.setattr(
            app_module.RENDER_HANDLE_CACHE,
            "close_all",
            lambda: events.append("close_all"),
        )
        monkeypatch.setattr(
            window._document,
            "save",
            lambda: events.append("save"),
        )

        window._save()

        assert events == ["close_all", "save"]
    finally:
        window._document.close_document()


def test_rename_file_releases_cached_render_handles_before_cleanup(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    source_path = tmp_path / "rename-handles.pdf"
    target_path = tmp_path / "renamed-handles.pdf"
    _create_sample_pdf(source_path)

    window = MainWindow()
    try:
        window._thread_pool = _NoOpThreadPool()
        window._open_document(source_path)

        calls: list[str] = []
        monkeypatch.setattr(
            app_module.RENDER_HANDLE_CACHE,
            "close_all",
            lambda: calls.append("close_all"),
        )
        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            staticmethod(
                lambda *_args, **_kwargs: (
                    str(target_path),
                    "PDF Files (*.pdf)",
                ),
            ),
        )

        window._rename_file()

        assert calls == ["close_all"]
        assert source_path.exists() is False
        assert window._document.source_path == target_path
    finally:
        window._document.close_document()
