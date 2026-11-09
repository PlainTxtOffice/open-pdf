# Open PDF for Linux

Open PDF is a Python/Qt PDF viewer and light editor for Linux. It supports
tabbed documents, search, bookmarks, notes, page editing, redaction, printing,
and optional Tesseract OCR. The PDF engine is PyMuPDF.

This implementation has its own package, dependencies, tests, storage adapters,
and build tooling. It does not import or compile the Windows project or the
experimental Rust PDF engine.

## Download and run

The **Linux build** GitHub Actions workflow targets **Ubuntu 24.04 x86-64** with
Python 3.14. Once the changes are published, run it from the Actions tab. It
also runs after Linux changes reach `main` and on pull requests. Successful runs
provide the `open-pdf-linux-x86_64` artifact containing a `.tar.gz` archive.
Hosted build and runtime verification remain pending until the first run.

Extract the archive and run `./open-pdf` from the extracted folder. Keep the
entire folder together: its Qt plugins and shared libraries are required.
Python is bundled; a separate Python installation is not needed.

The target machine needs a graphical desktop and the Qt runtime libraries:

```bash
sudo apt-get install libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 \
  libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 \
  libxcb-xinerama0 libxcb-xkb1 libx11-xcb1 libdbus-1-3 \
  libfontconfig1 libfreetype6 fonts-dejavu-core
```

Start under X11, or use XWayland from a Wayland desktop. Native Wayland sessions
and other distributions are not yet verified. Linux binaries depend on the build
system's libraries, so this archive is not advertised as universal. See
[Nuitka's Linux portability guidance](https://nuitka.net/user-documentation/common-issue-solutions.html#linux-standalone).

The included desktop entry expects `open-pdf` on `PATH`. To register it
manually, add the extracted folder to your `PATH`, copy the desktop entry to
`~/.local/share/applications/`, and copy `open_pdf/assets/open_pdf.png` to
`~/.local/share/icons/hicolor/256x256/apps/com.plaintxtoffice.OpenPDF.png`.
Create those directories if needed. No automatic desktop or MIME changes occur.

## Run from source

From `platform/linux/` on Linux:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,ocr]'
.venv/bin/python -m open_pdf.main /path/to/document.pdf
```

For OCR, install Tesseract and the needed language packs separately:

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

The build includes the Python OCR wrappers, but the Tesseract executable and
language data remain system dependencies. Without them, ordinary PDF viewing
and editing work and OCR actions explain the missing setup.

## Storage and passwords

Source and compiled launches use the same Linux locations:

| Content | Default location | Override |
| --- | --- | --- |
| Preferences | `~/.config/open-pdf/` | `XDG_CONFIG_HOME` |
| Existing OCR cache | `~/.cache/open-pdf/ocr/` | `XDG_CACHE_HOME` |
| Logs | `~/.local/state/open-pdf/logs/` | `XDG_STATE_HOME` |

Overrides must be absolute paths. The application does not write beside the
executable or migrate Windows data. Removing the executable leaves user data.

Remembered PDF passwords use the desktop **Secret Service** keyring, such as
GNOME Keyring. No password file or plaintext fallback is used. If the keyring
is absent, unavailable, or cannot be unlocked, enter the password when opening
the PDF. Filenames remain case-sensitive in the keyring. Passwords do not travel
with the extracted application folder.

## Validate and build

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy open_pdf
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest
sudo apt-get install build-essential patchelf xvfb xauth
.venv/bin/python -m pip install -e '.[dev,build,ocr]'
xvfb-run -a .venv/bin/python scripts/build.py
```

The build retains compiler intermediates in `build/nuitka/`. It smoke-tests the
compiled app by opening a temporary PDF, rendering its first page, and exiting.
The smoke test uses temporary XDG directories and does not change your settings.
The archive is created only after that test passes. Archiving before upload
preserves Linux executable permissions.

GitHub Actions uses free Nuitka and does not need private credentials. These
artifacts do not enable Nuitka Commercial code protection. No GitHub release is
published automatically. The workflow uses read-only repository permissions.

The source icon is repository `assets/icons/open_pdf.svg`. Regenerate the
checked-in Linux PNG with `.venv/bin/python scripts/generate_icon.py` after an
SVG change. Ordinary builds use the existing PNG without conversion tools.

## License

Open PDF's original code is MIT licensed. PyMuPDF/MuPDF have separate AGPL or
commercial terms; Qt and other dependencies also retain their licenses. See
[third-party notices](THIRD_PARTY.md) and the repository's `LICENSE`.
