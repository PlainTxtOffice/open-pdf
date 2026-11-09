"""Generate the macOS icon catalog and ICNS from the repository SVG."""

from __future__ import annotations

import json
import struct
from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

PROJECT = Path(__file__).resolve().parents[1]
SVG = PROJECT.parents[1] / "assets/icons/open_pdf.svg"
CATALOG = PROJECT / "assets/Assets.xcassets/AppIcon.appiconset"
ICON_TYPES = {16: b"icp4", 32: b"icp5", 64: b"icp6", 128: b"ic07",
              256: b"ic08", 512: b"ic09", 1024: b"ic10"}


def render_icon(renderer: QSvgRenderer, pixels: int, output: Path) -> None:
    """Render a transparent, square PNG at one required size."""
    image = QImage(pixels, pixels, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, pixels, pixels))
    painter.end()
    if not image.save(str(output), "PNG"):
        raise RuntimeError(f"Could not write {output}")


def main() -> None:
    """Write generated PNGs, catalog metadata, and the bundle ICNS."""
    renderer = QSvgRenderer(str(SVG))
    if not renderer.isValid():
        raise ValueError(f"Invalid source icon: {SVG}")
    CATALOG.mkdir(parents=True, exist_ok=True)
    for pixels in ICON_TYPES:
        render_icon(renderer, pixels, CATALOG / f"icon_{pixels}.png")
    images = [
        {"idiom": "mac", "size": f"{size}x{size}", "scale": f"{scale}x",
         "filename": f"icon_{size * scale}.png"}
        for size in (16, 32, 128, 256, 512) for scale in (1, 2)
    ]
    metadata = {"images": images, "info": {"version": 1, "author": "xcode"}}
    (CATALOG / "Contents.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n",
    )
    (CATALOG.parent / "Contents.json").write_text(
        '{"info": {"version": 1, "author": "xcode"}}\n',
        encoding="utf-8", newline="\n",
    )
    chunks = []
    for pixels, icon_type in ICON_TYPES.items():
        data = (CATALOG / f"icon_{pixels}.png").read_bytes()
        chunks.append(icon_type + struct.pack(">I", len(data) + 8) + data)
    payload = b"".join(chunks)
    (PROJECT / "assets/open_pdf.icns").write_bytes(
        b"icns" + struct.pack(">I", len(payload) + 8) + payload,
    )
    assets = PROJECT / "open_pdf/assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "open_pdf.png").write_bytes((CATALOG / "icon_256.png").read_bytes())


if __name__ == "__main__":
    main()
