# Open PDF for macOS

This initial macOS port includes the tabbed Qt/PyMuPDF viewer and light editor,
with Finder document opening, native menus and Command shortcuts, Keychain
password storage, and macOS application folders. The source and tests are
implemented; a native Mac build and manual acceptance pass are still required.

## Run from source

From `platform/mac_os/` on a Mac with Python 3.12 through 3.15:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,build,ocr]'
.venv/bin/python -m open_pdf.main
.venv/bin/python -m open_pdf.main ~/Documents/first.pdf ~/Documents/second.pdf
```

The optional OCR extra installs Python wrappers. Install Tesseract separately to
use OCR. The app checks `TESSERACT_CMD`, `PATH`, `/opt/homebrew/bin/tesseract`,
and `/usr/local/bin/tesseract`, including when started from Finder.

## Build an app

Build on the target Mac architecture with native Python and dependencies.
Supply your actual reverse-DNS bundle identifier; the example is a placeholder.

```sh
.venv/bin/python scripts/build.py --bundle-id your.organization.openpdf
```

The result is `dist/Open PDF.app`. The script uses PyInstaller and the committed
generated icon; it does not need the Windows or Linux project. Builds without
`--codesign-identity` use ad-hoc signing for local testing. For distribution,
supply an Apple Developer ID identity and separately notarize and staple the
app using your Apple account. This repository does not provision certificates
or perform notarization. Build separately for Apple Silicon and Intel; a build
on one architecture does not establish support for the other.

Finder integration declares the PDF type as an alternate editor, so building
the app does not change the user's default PDF application. Double-clicking a
document, Open With, and dropping files on the Dock icon use Qt file-open
events. Closing the last window exits this initial version; Quit prompts for
unsaved changes across its tabs.

## Storage

| Content | Location |
| --- | --- |
| UI settings | `~/Library/Application Support/Open PDF/ui-state.json` |
| Existing OCR result cache | `~/Library/Caches/Open PDF/ocr/` |
| Logs | `~/Library/Logs/Open PDF/` |
| Remembered PDF passwords | macOS Keychain, service `Open PDF document passwords` |

These paths apply to both source and packaged launches. The app never writes
settings inside its bundle. When Keychain access is denied, manual password
entry remains available and no password file is written.

## Development and validation

```sh
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy open_pdf
.venv/bin/python -m pytest
.venv/bin/rumdl check .
```

Tests isolate writable storage and replace credential access with an in-memory
backend. They cover document rendering/editing plus native integration
contracts. Offscreen tests on Windows cannot establish Cocoa behavior,
Keychain access, printing, Gatekeeper acceptance, or app packaging.

See [port notes and the Mac acceptance checklist](dev-docs/PORT.md). The
[shared user manual](../../docs/USER_MANUAL.md) documents Windows and Linux;
use this file for macOS setup and storage differences.

## License and references

Original application code is MIT licensed; PyMuPDF/MuPDF retain their
[AGPL or commercial licensing terms](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright).
Those terms still apply to this port and its packaged app.

- [Qt file-open events and bundle document declarations](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QFileOpenEvent.html)
- [Qt standard keyboard shortcuts](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QKeySequence.html)
- [Keyring macOS backend](https://keyring.readthedocs.io/en/stable/)
- [PyInstaller macOS bundles, events, and signing](https://pyinstaller.org/en/stable/feature-notes.html)
