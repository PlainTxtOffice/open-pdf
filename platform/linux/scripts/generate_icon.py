"""Render the shared SVG into the Linux package's generated PNG icon."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def main() -> None:
    """Generate the icon without requiring a graphical display."""
    project = Path(__file__).resolve().parents[1]
    source = project.parents[1] / "assets/icons/open_pdf.svg"
    target = project / "open_pdf/assets/open_pdf.png"
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG: {source}")
    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(target)):
        raise RuntimeError(f"Could not save {target}")


if __name__ == "__main__":
    main()
