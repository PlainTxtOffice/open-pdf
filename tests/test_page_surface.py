import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from src.domains.document.models import PdfPageLink
from src.gui.views.rendering.page_surface import PageSurfaceLabel


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _render_surface(surface: PageSurfaceLabel) -> QImage:
    image = QImage(surface.size(), QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    surface.render(image)
    return image


def _send_mouse_event(
    widget: QWidget,
    event_type: QEvent.Type,
    position: QPoint,
    button: Qt.MouseButton = Qt.MouseButton.NoButton,
) -> None:
    """Deliver a mouse event straight to `widget`.

    `QTest.mouseMove` and `QTest.mouseClick` inject events through the window
    system using *global* coordinates. Under the offscreen platform every
    top-level widget is placed at the same geometry, so the window shown
    first swallows the event and the widget under test never receives it.
    That made this test pass alone and fail after any earlier test had shown
    a window. Sending directly to the widget keeps delivery deterministic
    while still exercising the real event handlers.
    """
    buttons = (
        Qt.MouseButton.NoButton
        if event_type == QEvent.Type.MouseMove
        else button
    )
    event = QMouseEvent(
        event_type,
        QPointF(position),
        widget.mapToGlobal(QPointF(position)),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, event)


def test_text_overlay_hover_shows_link_feedback_and_keeps_clickable() -> None:
    app = _app()
    link = PdfPageLink(
        bounds=(20.0, 30.0, 140.0, 55.0),
        target_page_index=1,
    )
    activated_links: list[PdfPageLink] = []
    surface = PageSurfaceLabel()
    pixmap = QPixmap(200, 120)
    pixmap.fill(QColor("white"))
    surface.setPixmap(pixmap)
    surface.resize(204, 124)
    surface.set_page_links([link])
    surface.set_text_selection_enabled(enabled=True)
    surface.link_activated.connect(activated_links.append)
    surface.show()
    app.processEvents()

    before_hover = _render_surface(surface)
    _send_mouse_event(
        surface.text_layer(),
        QEvent.Type.MouseMove,
        QPoint(80, 42),
    )
    app.processEvents()
    after_hover = _render_surface(surface)

    assert (
        surface.text_layer().cursor().shape()
        == Qt.CursorShape.PointingHandCursor
    )
    assert before_hover != after_hover

    _send_mouse_event(
        surface.text_layer(),
        QEvent.Type.MouseButtonPress,
        QPoint(80, 42),
        Qt.MouseButton.LeftButton,
    )
    _send_mouse_event(
        surface.text_layer(),
        QEvent.Type.MouseButtonRelease,
        QPoint(80, 42),
        Qt.MouseButton.LeftButton,
    )
    app.processEvents()

    assert activated_links == [link]
