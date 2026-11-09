"""Guard the inward dependency direction, including type-only imports."""

import ast
from pathlib import Path


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"Use explicit imports for boundary checks: {path}"
            names.add(node.module or "")
    return names


def test_domains_use_only_pure_dependencies():
    allowed = {"__future__", "typing", "dataclasses", "collections.abc"}
    violations = [
        (str(path), name)
        for path in Path("open_pdf/domains").rglob("*.py")
        for name in imports(path)
        if name not in allowed and not name.startswith("open_pdf.domains.")
    ]
    assert violations == []
    assert not Path("open_pdf/domains/__init__.py").exists()


def test_adapters_do_not_depend_on_workflows_or_gui():
    violations = [
        (str(path), name)
        for path in Path("open_pdf/adapters").rglob("*.py")
        for name in imports(path)
        if name.startswith(("open_pdf.application", "open_pdf.gui"))
    ]
    assert violations == []


def test_application_workflows_do_not_depend_on_gui():
    violations = [
        (str(path), name)
        for path in Path("open_pdf/application").rglob("*.py")
        for name in imports(path)
        if name.startswith(("open_pdf.gui", "PySide6"))
    ]
    assert violations == []
