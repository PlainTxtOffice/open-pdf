"""Structural guards over the GUI layer's outward dependencies."""

from __future__ import annotations

import ast
from pathlib import Path

GUI_ROOT = Path("src/gui")

# Modules that are allowed to reach past the GUI layer into an adapter or
# straight into pymupdf, as (module path, imported module) pairs.
#
# Keep this list exact. Adding a pair is a deliberate decision to widen the
# GUI layer's contact surface with the rest of the app, and
# `test_no_stale_integration_allowances` fails when a pair stops matching so
# that moving a module cannot silently retire its guard.
ALLOWED_INTEGRATION_IMPORTS = {
    ("src/gui/models/document_session.py", "pymupdf"),
    ("src/gui/models/window_state.py", "pymupdf"),
    ("src/gui/ocr/task.py", "src.adapters.document.pymupdf.processing"),
    ("src/gui/ocr/workflow.py", "src.adapters.ocr.results"),
    ("src/gui/views/rendering/page_render_cache.py", "pymupdf"),
    (
        "src/gui/views/rendering/page_render_cache.py",
        "src.adapters.document.pymupdf.qt",
    ),
    (
        "src/gui/views/rendering/page_rendering.py",
        "src.adapters.document.pymupdf.document",
    ),
    (
        "src/gui/views/rendering/page_rendering.py",
        "src.adapters.document.pymupdf.qt",
    ),
    ("src/gui/views/rendering/render_handle_cache.py", "pymupdf"),
    (
        "src/gui/views/rendering/thumbnail_rendering.py",
        "src.adapters.document.pymupdf.document",
    ),
    (
        "src/gui/views/rendering/thumbnail_rendering.py",
        "src.adapters.document.pymupdf.qt",
    ),
    (
        "src/gui/views/rendering/zoom/preview.py",
        "src.adapters.document.pymupdf.document",
    ),
    (
        "src/gui/views/root_window/panes/thumbnails.py",
        "src.adapters.document.pymupdf.qt",
    ),
    (
        "src/gui/views/root_window/persistence.py",
        "src.adapters.persistence.desktop",
    ),
    ("src/gui/views/root_window/window.py", "src.adapters.document.rename"),
    ("src/gui/views/root_window/window.py", "src.adapters.ocr.results"),
    (
        "src/gui/views/root_window/window.py",
        "src.adapters.persistence.desktop",
    ),
    ("src/gui/views/search/search_highlighting.py", "pymupdf"),
    ("src/gui/views/search/search_navigation.py", "pymupdf"),
    (
        "src/gui/views/search/search_task.py",
        "src.adapters.document.pymupdf.processing",
    ),
    (
        "src/gui/views/workflows/file_rename.py",
        "src.adapters.document.rename",
    ),
    (
        "src/gui/views/workflows/printing.py",
        "src.adapters.document.pymupdf.qt",
    ),
}


def _imported_modules(module_path: Path) -> list[str]:
    """Return every module name imported by one source file."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    return imported


def _is_integration_import(module: str) -> bool:
    """Report whether an import crosses out of the GUI layer."""
    return module == "pymupdf" or module.startswith("src.adapters.")


def _actual_integration_imports() -> set[tuple[str, str]]:
    """Collect every outward import the GUI layer makes today."""
    return {
        (module_path.as_posix(), imported)
        for module_path in GUI_ROOT.rglob("*.py")
        for imported in _imported_modules(module_path)
        if _is_integration_import(imported)
    }


def test_app_is_the_only_direct_gui_module() -> None:
    direct_modules = sorted(
        path.name for path in GUI_ROOT.glob("*.py") if path.name != "__init__.py"
    )

    assert direct_modules == ["app.py"]


def test_gui_components_do_not_import_composition_root() -> None:
    importing_modules = sorted(
        module_path.as_posix()
        for module_path in GUI_ROOT.rglob("*.py")
        if module_path.name != "app.py"
        and "src.gui.app" in _imported_modules(module_path)
    )

    assert importing_modules == []


def test_gui_adapter_imports_are_explicit() -> None:
    unexpected = sorted(
        _actual_integration_imports() - ALLOWED_INTEGRATION_IMPORTS
    )

    assert unexpected == [], (
        "GUI modules reached outside the GUI layer without an allowance. "
        "Route the call through an existing seam, or add the pair to "
        "ALLOWED_INTEGRATION_IMPORTS deliberately: "
        f"{unexpected}"
    )


def test_no_stale_integration_allowances() -> None:
    """Fail when an allowance no longer matches a real import.

    A stale entry means a module moved or dropped the import, and the guard
    silently stopped protecting anything. Without this check the allowlist
    rots into a list of paths that no longer exist.
    """
    stale = sorted(ALLOWED_INTEGRATION_IMPORTS - _actual_integration_imports())

    assert stale == [], (
        "ALLOWED_INTEGRATION_IMPORTS lists imports that no longer exist. "
        "Remove or repoint these entries: "
        f"{stale}"
    )
