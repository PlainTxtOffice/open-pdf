# Open PDF for Windows

Developer setup for the Windows desktop viewer. You need Windows and Python 3.12
or newer.

Run these commands from `platform/windows/`:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe -m open_pdf.main
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m mypy open_pdf
.venv/Scripts/rumdl.exe check
```

To open a PDF at startup, pass its path:

```powershell
.venv/Scripts/python.exe -m open_pdf.main "C:/Users/YourName/Documents/report.pdf"
```

Application modules live in `open_pdf/` and use imports such as
`open_pdf.config.path_handler`. The window icon and bundled fonts live in
`assets/`; README screenshots live in `assets/screenshots/` and are excluded
from builds. Development data and logs are relative to this Windows project
folder. Add application tests under `tests/`.

Build scripts live in `scripts/nuitka/`; see the
[Nuitka build guide](scripts/nuitka/README.md).

See the [repository README](../../README.md) for project-wide documentation.

## Architecture

- `open_pdf/domains/document/` owns engine-independent rules and values for
  page indexes, navigation, notes, text matching, and metadata normalization.
- `open_pdf/application/document/` coordinates opening, editing, saving, notes,
  OCR, and rename workflows. `session.PdfDocument` remains the document facade
  used by the GUI; it coordinates state updates after successful operations.
- `open_pdf/adapters/` owns PyMuPDF operations, filesystem access, OCR engines,
  persistence, and Windows integration. The PDF adapter is split into
  lifecycle, rendering, links, and content operations.
- `open_pdf/gui/` owns Qt presentation, selection, and dialogs. Text editing
  presentation lives in `views/workflows/text_editing.py`, and page selection
  lives in `views/rendering/selection.py`.

The GUI calls application workflows; workflows use domain rules and adapters.
Domain modules never import outer layers, and adapters never import application
workflows or GUI modules. Search rectangles cross boundaries as four-coordinate
tuples in PDF units, not engine objects.

Startup explicitly migrates legacy storage folders and selects portable or
installed storage before importing logging and GUI consumers. Importing
`config/path_handler.py` alone does not create or move storage folders.

Run `tests/test_architecture.py` and `tests/test_gui_imports.py` to check these
boundaries, alongside the behavioral regression tests.

Pytest isolates temporary files and its cache by project and process account
through `conftest.py`. Run it without a fixed `--basetemp` so Windows user
and sandbox accounts do not share permission-sensitive test directories.
