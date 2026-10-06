---
last_updated: 2026-09-15
---

# Open PDF

Lightweight desktop PDF viewer with room for basic editing features, built
with [PySide6](https://wiki.qt.io/Qt_for_Python) and
[PyMuPDF](https://pymupdf.readthedocs.io/).

![Open PDF main window](assets/open-pdf-main-window.png)

Open PDF is a no-frills desktop reader for PDF files. Open a document from
your file manager or the command line, scroll the whole file continuously,
switch to a one-page-at-a-time view, search across the document, follow
built-in bookmarks, and copy selectable text — without waiting for the entire
PDF to rasterize up front. Light editing is there when you need it: redact a
region, replace a line of text, reorder or insert pages, and save the result
back over the original.

For a step-by-step walkthrough and full feature reference, see the
[User Manual](docs/USER_MANUAL.md).

## Getting started

Requires Python 3.12 or newer.

1. Clone the repository and create a virtual environment.
1. Install the project in editable mode:

   ```powershell
   pip install -e .
   ```

1. Launch the app:

   ```powershell
   open-pdf
   ```

1. Or open a PDF directly at launch:

   ```powershell
   open-pdf path/to/file.pdf
   ```

Launching a second time while the app is already running activates the
existing window and forwards the requested PDF to it, rather than starting a
new process.

## Building a Windows executable

Nuitka build scripts live in `dev-docs/packaging/nuitka/` and use the
repository's `.venv` as the build interpreter. The two scripts produce the two
distributable shapes:

```powershell
./dev-docs/packaging/nuitka/onefile.ps1     # portable
./dev-docs/packaging/nuitka/standalone.ps1  # to feed an installer
```

`onefile.ps1` writes `build/onefile/Open PDF.exe`, a single portable
executable that keeps its settings, logs, and caches in an `Open PDF Data`
folder beside itself. Run it from a USB stick and it leaves nothing behind on
the host machine.

`standalone.ps1` writes an unpacked `build/standalone/` directory to hand to
an installer. That build keeps per-user state in `%LOCALAPPDATA%\Open PDF`, so
it does not need a writable installation directory.

The difference is a `portable.marker` file that `onefile.ps1` bundles into the
build and `standalone.ps1` leaves out — nothing at runtime switches modes, so
an installed copy cannot become portable by accident.

## Features

### Reading

- Open a PDF from disk or via the command line
- Several documents open at once in tabs you can drag to reorder
- Continuous scrolling view of the full document
- Single-page view for one-page-at-a-time reading with `Up` / `Down` page
  steps
- Navigate with the page-number jump, the thumbnails pane, the bookmarks
  pane, or by clicking links inside the PDF
- Zoom with `Actual Size`, `Fit Width`, `Fit Page`, or `Ctrl + mouse wheel`
  centered on the pointer
- Full-document text search that updates as you type, with jump-between-matches
- Copy selectable text from the extracted text pane or the page overlay
- Remembers passwords for encrypted PDFs, stored protected on Windows

### Editing

- Edit PDF mode: drag out a page region, then `Remove Content` to redact it
  or `Replace Text...` to rewrite the text it covers
- Insert a blank page before or after the current page, sized to match its
  neighbour
- Reorder pages with the arrow buttons above the thumbnails pane
- Rotate or delete a page from the thumbnail context menu
- Add bookmarks from selected text, then rename or delete them
- Edit PDF Info Dictionary fields and raw XMP metadata
- Write plain-text notes that are stored as `notes.txt` inside the PDF
- Optional Tesseract OCR for one page or the whole document, cached per
  source file so results survive reopening

### Files

- Save in place, `Save As` a copy, or `Rename File` to move the document to a
  new name
- Print all pages, the current page, or a page range

### Under the hood

- Lazy rendering: only visible pages are rasterized, and far-off page images
  are evicted from memory automatically
- Unhandled errors are routed to a crash dialog that names the log file

## Glossary

Terminology used throughout the app and its documentation:

- **menu bar**: the top application menu strip
- **tool bar**: the strip below the menu bar with page, zoom, and search
  controls
- **page thumbnails**: the pane that lists page previews for direct
  navigation
- **document view**: the central scrolling PDF surface
- **bookmarks**: the pane that shows the PDF outline/tree
- **notes**: the editable plain-text pane stored inside the active PDF
- **status bar**: the strip along the bottom of the main window
- **Read Mode**: the normal interaction mode, where dragging selects text
- **Edit PDF mode**: the interaction mode where dragging selects a page
  region to redact or replace

## Roadmap

Planned next steps:

- Annotation tools
- Better on-page text selection and annotation handles
- Keyboard shortcuts for page stepping, zoom, and back/forward history, which
  currently exist as actions with no binding

## License

This project is licensed under the
[GNU Affero General Public License v3.0 or later](LICENSE).

That choice is intentional: Open PDF depends on PyMuPDF, which is offered
under AGPL or a commercial license. Using AGPL for this repository keeps the
source distribution aligned with the open-source PyMuPDF licensing model.
